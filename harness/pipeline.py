"""阶段机：把「跑哪几个阶段、谁进哪个阶段」写成数据。

## 为什么要有这一层

原先是 `runner.run_llm_loop` 里硬编码的：

```text
级联 → for rnd in 1..rounds: 问模型 → 编译
```

要加 L2（检索）、L3（Planner）就只能改主干，越改越乱。现在改成：

```python
PIPELINE_V1 = [
    Stage("L0", stage_cascade, triggers=frozenset()),        # 全部未解决题
    Stage("remedy", stage_remedy, triggers=REMEDY_TRIGGERS), # 只跑限制类失败
    Stage("L1", stage_model, triggers=frozenset(), repeat=budget.max_rounds),
]
```

以后加 L2 只需要 append 一个 `Stage`，并给它一个 `triggers`。

## 约定

每个 stage 函数签名统一为 `(states: list[ProblemState], ctx: Context) -> None`，
**只处理传进来的子集**，并在内部把 attempt 追加到 `st.attempts` 上。
选谁进这一阶段由 `run_pipeline` 负责，stage 自己不需要判断状态。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from . import config, runner
from .cascade import cascade_proof
from .models import Attempt, ModelClient, ModelError, ProposeRequest
from .problems import Problem


@dataclass
class Context:
    """一次运行共享的上下文（相当于轻量黑板）。"""

    run_id: str
    chunk_size: int = 60
    attempt_round: int = 0
    use_hints: bool = False
    deep: bool = False
    #: 单题 token 预算；超出的题不再进入后续 L1 轮
    max_tokens: int = 20_000
    #: 整批墙钟预算（秒）；到点后不再开新的 L1 轮
    max_wall_s: float = 0.0
    deadline: float = 0.0
    #: 判定后端：None = 批量编译（真相来源）；传一个 judge 则用它做快速判定，
    #: 最后再统一跑一次批量编译做终审。
    judge: Callable[[runner.ProblemState], bool] | None = None
    judge_name: str = ""
    #: 是否允许 Prover 返回带 sorry 的骨架（只影响 prompt 与记账，不影响 verified）
    allow_skeleton: bool = False
    #: Loogle 检索客户端；None = 不检索
    retrieval: object | None = None
    log: Callable[[str], None] = print

    def __post_init__(self) -> None:
        # 由 max_wall_s 推出截止时刻；显式传 deadline 时以 deadline 为准
        if self.max_wall_s and not self.deadline:
            self.deadline = time.monotonic() + self.max_wall_s

    def next_round(self) -> int:
        self.attempt_round += 1
        return self.attempt_round

    def over_deadline(self) -> bool:
        return bool(self.deadline) and time.monotonic() > self.deadline


# --------------------------------------------------------------------- stages
def stage_cascade(states: list[runner.ProblemState], ctx: Context) -> None:
    """L0：便宜的定式 tactic 组合，整套写在一个 `first` 里。"""
    proof = cascade_proof(deep=ctx.deep)
    for st in states:
        st.attempts.append({"round": 0, "source": "cascade", "proof": proof})
        st.stages.append("L0")
    runner._compile_chunks(
        states,
        work_prefix=f"{ctx.run_id}-L0",
        chunk_size=ctx.chunk_size,
        log_dir=config.RUNS_DIR,
        source="cascade",
    )


def stage_remedy(states: list[runner.ProblemState], ctx: Context) -> None:
    """补救：用同一套 tactic，但把限制类 option 放开。

    只对 `max_rec_depth` / `exponent_threshold` 触发的题有意义；
    `maxHeartbeats` 必须在 `REMEDY_OPTIONS` 里且**有界**，否则 simp 会跑飞。
    """
    proof = cascade_proof(deep=ctx.deep)
    for st in states:
        st.attempts.append(
            {
                "round": 1,
                "source": "cascade-remedy",
                "proof": proof,
                "extra_options": list(config.REMEDY_OPTIONS),
            }
        )
        st.stages.append("remedy")
    runner._compile_chunks(
        states,
        work_prefix=f"{ctx.run_id}-remedy",
        chunk_size=ctx.chunk_size,
        log_dir=config.RUNS_DIR,
        source="cascade-remedy",
        extra_options=config.REMEDY_OPTIONS,
        timeout_s=config.REMEDY_TIMEOUT_S,
    )


def stage_model(
    states: list[runner.ProblemState], ctx: Context, *, model: ModelClient
) -> None:
    """L1：逐题问模型要 tactics，再把所有候选拼成一批编译（或交给 worker 判）。"""
    from . import roles as _roles
    from .retrieval import extract_query_terms

    rnd = ctx.next_round()
    prepared: list[runner.ProblemState] = []
    api_errors = 0

    for st in states:
        history = _attempts_of(st)

        # 检索：只在需要时触发，且失败不影响主循环
        candidates: list[str] = []
        if ctx.retrieval is not None:
            should = st.critic_label == "missing_lemma" or st.failed_rounds >= 1
            if should:
                diag = (st.attempts[-1].get("diagnostics", "") if st.attempts else "") or ""
                terms = extract_query_terms(diag, *st.plan.get("lemmas", []))
                try:
                    res = ctx.retrieval.retrieve_for(terms=terms)  # type: ignore[attr-defined]
                    st.retrieval = res.as_record()
                    block = res.as_prompt_block()
                    candidates = [block] if block else []
                except Exception:  # noqa: BLE001 检索是辅助，绝不阻塞
                    st.retrieval = {"queries": 0, "hits": 0, "failed": 1}

        plan_text = ""
        if st.plan:
            outline = st.plan.get("outline") or []
            lemmas = st.plan.get("lemmas") or []
            plan_text = "\n".join(f"{i + 1}. {x}" for i, x in enumerate(outline))
            if lemmas:
                plan_text += "\n可用引理：" + ", ".join(lemmas)
            if st.plan.get("pitfalls"):
                plan_text += "\n注意：" + st.plan["pitfalls"]

        try:
            resp = model.propose(
                ProposeRequest(
                    problem=st.problem,
                    attempt_index=rnd - 1,
                    history=history,
                    hints=ctx.use_hints,
                    # 黑板上 Critic/Strategist 的产物只进 prompt，不进 Lean。
                    # **必须带 critic_note**：只传标签等于没传（v0.5 的教训——
                    # Critic 写了"需补 x²+y² 展开"，但 Prover 只看到 `unsolved`）。
                    critic_label=st.critic_label,
                    critic_note=st.critic_note,
                    strategy=st.strategy,
                    plan=plan_text,
                    plan_version=st.plan_version,
                    candidates=candidates,
                    allow_skeleton=ctx.allow_skeleton,
                )
            )
        except ModelError as exc:
            # 单题调用失败不能让整轮崩掉
            api_errors += 1
            kind = f"api_error:{exc.kind}"
            st.attempts.append(
                {
                    "round": 100 + rnd,
                    "source": model.name,
                    "proof": "",
                    "status": "error",
                    "error_kind": kind,
                    "diagnostics": exc.detail[:2000],
                    "tokens_in": 0,
                    "tokens_out": 0,
                }
            )
            st.status = "error"
            if kind not in st.error_types:
                st.error_types.append(kind)
            continue

        # 上一轮若整轮 API 失败，题目状态停在 error；本轮拿到结果后回到 failed
        if st.status == "error":
            st.status = "failed"
        st.tokens_in += resp.tokens_in
        st.tokens_out += resp.tokens_out
        st.attempts.append(
            {
                "round": rnd,
                "source": model.name,
                "proof": resp.proof,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
            }
        )
        st.stages.append(f"L1#{rnd}")
        prepared.append(st)

    if not prepared:
        ctx.log(f"[warn] 第 {rnd} 轮全部 {api_errors} 次模型调用失败，提前结束")
        raise StopIteration

    # 快速判定：常驻 worker 一条 0.2 s，批量编译一轮要几分钟。
    if ctx.judge is not None:
        accepted = 0
        for st in prepared:
            if ctx.judge(st):
                st.status = "verified"
                st.proof = st.attempts[-1]["proof"]
                st.axioms = ()
                st.error_types = []
                accepted += 1
            else:
                st.status = "failed"
                kind = st.attempts[-1].get("error_kind") or "tactic_failed"
                if kind not in st.error_types:
                    st.error_types.append(kind)
                # 带 sorry 的可编译骨架算进展（但不算通过）
                _record_progress(st, rnd)
        ctx.log(f"[{ctx.judge_name}] 第 {rnd} 轮：{accepted}/{len(prepared)} 通过（待终审）")
        skeletons = sum(1 for st in prepared if st.best_skeleton)
        if ctx.allow_skeleton and skeletons:
            ctx.log(f"[skeleton] 累计 {skeletons}/{len(prepared)} 题拿到可编译骨架")
        _bump_failed_rounds(prepared)
        return

    # 模型生成的证明可能混进极慢的 tactic。实测一个 60 题批次跑满 30 分钟，
    # 正好贴着默认超时线——再慢一点整块就会被判 batch_timeout。
    # 设 `MINIF2F_L1_MAX_HEARTBEATS` 可给 L1 批次单独加心跳上限。
    l1_opts: tuple[str, ...] = ()
    if config.L1_MAX_HEARTBEATS > 0:
        l1_opts = (f"maxHeartbeats={config.L1_MAX_HEARTBEATS}",)

    runner._compile_chunks(
        prepared,
        work_prefix=f"{ctx.run_id}-L1-{rnd}",
        chunk_size=ctx.chunk_size,
        log_dir=config.RUNS_DIR,
        source=model.name,
        extra_options=l1_opts,
    )
    _bump_failed_rounds(prepared)


def _bump_failed_rounds(states: list[runner.ProblemState]) -> None:
    """给仍在失败的题累加轮数（Strategist 的门控用它）。"""
    for st in states:
        if st.status != "verified":
            st.failed_rounds += 1


# ------------------------------------------------------------ critic / strategist
def _attempts_of(st: runner.ProblemState) -> list[Attempt]:
    return [
        Attempt(
            source=a["source"],
            proof=a["proof"],
            status=a.get("status", "unknown"),
            error_kind=a.get("error_kind", "none"),
            diagnostics=a.get("diagnostics", ""),
        )
        for a in st.attempts
    ]


def stage_critic(states: list[runner.ProblemState], ctx: Context, *, model: ModelClient) -> None:
    """Critic：只对失败的题做**闭集分类**，不写代码、不改证明。"""
    from . import roles

    rnd = ctx.attempt_round
    for st in states:
        history = _attempts_of(st)
        try:
            resp = model.propose(
                ProposeRequest(
                    problem=st.problem,
                    attempt_index=rnd,
                    history=history,
                    role="critic",
                )
            )
        except ModelError as exc:
            st.critic_label = "other"
            st.critic_note = f"api_error:{exc.kind}"
            continue
        label, note = roles.parse_critic(resp.text or resp.proof)
        st.critic_label = label
        st.critic_note = note
        st.tokens_in += resp.tokens_in
        st.tokens_out += resp.tokens_out
        st.stages.append(f"critic#{rnd}")
    ctx.log(f"[critic] 第 {rnd} 轮分类：{_label_hist(states)}")


def stage_strategist(
    states: list[runner.ProblemState], ctx: Context, *, model: ModelClient
) -> None:
    """Strategist：给**策略文本**，只进 Prover 的 prompt，永不直接编译。"""
    from . import roles

    rnd = ctx.attempt_round
    for st in states:
        history = _attempts_of(st)
        try:
            resp = model.propose(
                ProposeRequest(
                    problem=st.problem,
                    attempt_index=rnd,
                    history=history,
                    role="strategist",
                    critic_label=st.critic_label,
                )
            )
        except ModelError:
            continue
        strategy, sketch = roles.parse_strategist(resp.text or resp.proof)
        st.strategy = strategy if not sketch else f"{strategy}\n{sketch}"
        st.tokens_in += resp.tokens_in
        st.tokens_out += resp.tokens_out
        st.stages.append(f"strategist#{rnd}")
    ctx.log(f"[strategist] 第 {rnd} 轮：{sum(1 for s in states if s.strategy)}/{len(states)} 给出策略")


def _label_hist(states: list[runner.ProblemState]) -> dict[str, int]:
    out: dict[str, int] = {}
    for st in states:
        out[st.critic_label or "none"] = out.get(st.critic_label or "none", 0) + 1
    return out


def needs_critic(st: runner.ProblemState) -> bool:
    """Critic 只在「有失败尝试」的题上有意义。"""
    return st.status != "verified" and bool(st.attempts)


def needs_strategist(st: runner.ProblemState) -> bool:
    """**门控**：只有策略类失败或连续失败够多时才叫 Strategist。

    不门控会被延迟拖死——每轮都对所有题调用，等于给 L1 加了一倍成本。
    """
    from .roles import STRATEGY_LABELS

    if st.status == "verified":
        return False
    return st.critic_label in STRATEGY_LABELS or st.failed_rounds >= 3


def needs_plan(st: runner.ProblemState) -> bool:
    """计划调度：第 0 轮生成 v1，之后只在 2^n 检查点重写。

    对齐 Numina-Lean-Agent 的做法：失败后要改的是**计划**，但不必每轮都改——
    每轮重写既贵又会把模型来回带偏。
    """
    if st.status == "verified":
        return False
    if not st.plan:
        return True
    return st.failed_rounds in config.PLAN_CHECKPOINTS


def stage_plan(states: list[runner.ProblemState], ctx: Context, *, model: ModelClient) -> None:
    """生成/重写证明计划。计划只进 prompt，不写 Lean。"""
    from . import roles

    made = 0
    for st in states:
        history = _attempts_of(st)
        try:
            resp = model.propose(
                ProposeRequest(
                    problem=st.problem,
                    attempt_index=st.failed_rounds,
                    history=history,
                    role="planner",
                    plan=st.plan.get("raw", ""),
                )
            )
        except ModelError:
            continue
        plan = roles.parse_plan(resp.text or resp.proof)
        st.plan = plan
        st.plan_version += 1
        st.plan_history.append({"version": st.plan_version, "at_round": st.failed_rounds})
        st.tokens_in += resp.tokens_in
        st.tokens_out += resp.tokens_out
        st.stages.append(f"plan#v{st.plan_version}")
        made += 1
    if made:
        ctx.log(f"[plan] 本轮生成/重写 {made} 份计划")


def _record_progress(st: runner.ProblemState, rnd: int) -> None:
    """把「带 sorry 的可编译骨架」记成进展（**不改变 verified**）。"""
    info = (st.attempts[-1].get("worker") if st.attempts else None) or {}
    if not info.get("compiles"):
        return
    sorries = int(info.get("sorries", 0))
    if sorries <= 0 or sorries > config.MAX_PROOF_SORRIES:
        return
    best = st.best_skeleton
    if best is None or sorries < int(best.get("sorries", 99)):
        st.best_skeleton = {
            "proof": st.attempts[-1].get("proof", ""),
            "sorries": sorries,
            "at_round": rnd,
        }


# --------------------------------------------------------------------- stages
@dataclass(frozen=True)
class Stage:
    name: str
    #: 触发条件：空集 = 所有未解决题；否则要求 error_types 与本集合有交集
    triggers: frozenset[str] = frozenset()
    repeat: int = 1
    #: 自定义实现（测试或未来的 L2/L3 用）；为空时按 name 分派到内置阶段
    fn: Callable[[list[runner.ProblemState], Context], None] | None = None
    #: 更细的触发条件（triggers 只能按 error_types 匹配，表达不了「轮数 + 标签」）
    predicate: Callable[[runner.ProblemState], bool] | None = None


def pipeline_v1(
    *,
    rounds: int,
    remediate: bool,
    critic: bool = False,
    strategist: bool = False,
    plan: bool = False,
) -> list[Stage]:
    """阶段计划。

    启用角色时**交错展开**：`L1 → Critic → Strategist` 每轮一组，
    这样 Critic 拿到的是本轮刚失败的诊断，而不是上一轮的旧信息。

    `plan=True` 时，第 0 轮之前插入 `plan` 阶段（生成 v1），之后每轮 L1 前面
    再插一个 `plan` 阶段——由 `needs_plan` 谓词决定是否真的重写（2^n 检查点）。
    """
    stages = [Stage("L0")]
    if remediate:
        stages.append(Stage("remedy", triggers=config.REMEDY_TRIGGERS))
    if plan:
        stages.append(Stage("plan", predicate=needs_plan))
    for _ in range(max(rounds, 0)):
        stages.append(Stage("L1"))
        if plan:
            stages.append(Stage("plan", predicate=needs_plan))
        if critic:
            stages.append(Stage("critic", predicate=needs_critic))
        if strategist:
            stages.append(Stage("strategist", predicate=needs_strategist))
    return stages


def run_pipeline(
    problems: Sequence[Problem],
    *,
    model: ModelClient | None,
    rounds: int = 2,
    remediate: bool = True,
    chunk_size: int = 60,
    use_hints: bool = False,
    deep: bool = False,
    max_tokens: int = 20_000,
    max_wall_s: float = 0.0,
    judge: str = "batch",
    critic: bool = False,
    strategist: bool = False,
    plan: bool = False,
    retrieval: bool = False,
    allow_skeleton: bool = False,
    label: str = "pipeline",
    allow_test: bool = False,
    out_path: Path | None = None,
    stages: Sequence[Stage] | None = None,
) -> tuple[Path, list[runner.ProblemState]]:
    """按阶段跑完一批题，返回 (记录路径, 每题状态)。

    预算：`max_rounds` 由阶段机的 `repeat` 强制；`max_tokens` 逐题拦截；
    `max_wall_s` 到点后不再开新的 L1 轮（已经开始的轮会跑完）。

    `judge="worker"` 时，L1 每轮用常驻 worker 快速判定，**最后再对通过者跑一次
    批量编译做终审**（worker 只是加速器，真相仍以批量审计为准）。
    """
    config.ensure_dirs()
    runner._guard_split(problems, allow_test=allow_test)
    run_id = runner._new_run_id(label)
    ctx = Context(
        run_id=run_id,
        chunk_size=chunk_size,
        use_hints=use_hints,
        deep=deep,
        max_tokens=max_tokens,
        max_wall_s=max_wall_s,
        allow_skeleton=allow_skeleton,
    )
    if retrieval:
        from .retrieval import LoogleClient

        ctx.retrieval = LoogleClient()

    worker = None
    if judge == "worker":
        from .worker import LeanWorker, binder_count, statement_type

        worker = LeanWorker(request_timeout_s=config.WORKER_CHECK_TIMEOUT_S)
        worker.start()
        ctx.log(f"[worker] 预热完成 {worker.warmup_s:.1f}s")

        def _judge(st: runner.ProblemState) -> bool:
            nonlocal worker
            proof = st.attempts[-1]["proof"]
            try:
                r = worker.check(
                    statement_type(st.problem.header),
                    proof,
                    nbinders=binder_count(st.problem.header),
                )
            except Exception as exc:  # worker 静默崩溃（原生栈溢出等）：重启并放弃这题
                ctx.log(f"[worker] 崩溃，重启：{str(exc).splitlines()[0][:80]}")
                worker.stop()
                worker = LeanWorker(request_timeout_s=config.WORKER_CHECK_TIMEOUT_S)
                worker.start()
                st.attempts[-1]["error_kind"] = "worker_crash"
                st.attempts[-1]["diagnostics"] = str(exc)[:500]
                return False
            # 把判定与诊断写回 attempt：下一轮拼 history 时模型就能看到反馈
            st.attempts[-1]["error_kind"] = r.reason
            st.attempts[-1]["diagnostics"] = r.error[:1000]
            st.attempts[-1]["status"] = "verified" if r.ok else "failed"
            # 骨架进展需要「能编译 + sorry 数」，在这里一并落盘
            st.attempts[-1]["worker"] = {
                "ok": r.ok,
                "sorries": r.sorries,
                "compiles": r.compiles,
                "goals": r.goals,
            }
            return r.ok

        ctx.judge = _judge
        ctx.judge_name = "worker"

    try:
        states = [runner.ProblemState(problem=p) for p in problems]
        plan_stages = (
            stages
            if stages is not None
            else pipeline_v1(
                rounds=rounds,
                remediate=remediate,
                critic=critic,
                strategist=strategist,
                plan=plan,
            )
        )

        for stage in plan_stages:
            for _ in range(stage.repeat):
                pending = [st for st in states if st.status != "verified"]
                if not pending:
                    break
                if stage.predicate is not None:
                    candidates = [st for st in pending if stage.predicate(st)]
                elif stage.triggers:
                    candidates = [st for st in pending if stage.triggers & set(st.error_types)]
                else:
                    candidates = pending
                if stage.name == "L1":
                    if ctx.over_deadline():
                        ctx.log(f"[budget] 墙钟预算 {max_wall_s:.0f}s 用尽，停止 L1")
                        break
                    before = len(candidates)
                    candidates = [
                        st for st in candidates if st.tokens_in + st.tokens_out <= ctx.max_tokens
                    ]
                    if before != len(candidates):
                        ctx.log(f"[budget] {before - len(candidates)} 道题超出 token 预算，跳过 L1")
                if not candidates:
                    continue
                if stage.fn is not None:
                    stage.fn(candidates, ctx)
                elif stage.name == "L0":
                    stage_cascade(candidates, ctx)
                elif stage.name == "remedy":
                    stage_remedy(candidates, ctx)
                elif stage.name == "L1":
                    if model is None:
                        raise ValueError("L1 需要 model")
                    try:
                        stage_model(candidates, ctx, model=model)
                    except StopIteration:
                        break
                elif stage.name == "critic":
                    if model is None:
                        raise ValueError("critic 需要 model")
                    stage_critic(candidates, ctx, model=model)
                elif stage.name == "strategist":
                    if model is None:
                        raise ValueError("strategist 需要 model")
                    stage_strategist(candidates, ctx, model=model)
                elif stage.name == "plan":
                    if model is None:
                        raise ValueError("plan 需要 model")
                    stage_plan(candidates, ctx, model=model)
                else:
                    raise ValueError(f"未知阶段：{stage.name}")

        # 终审：worker 放行的证明仍要走一遍批量编译 + 四项审计。
        # 用**小块 + 硬超时**：模型证明里常有极慢的 tactic，一整块 60 题撞上
        # 1800 s 上限会波及 60 道已通过的题；小块让它只影响 20 道，
        # 而且 `keep_on_timeout` 保证超时只记 `audit_timeout`、不推翻 worker 的判定。
        if worker is not None:
            approved = [st for st in states if st.status == "verified"]
            if approved:
                audit_chunk = min(chunk_size or 20, config.AUDIT_CHUNK_SIZE)
                ctx.log(
                    f"[终审] {len(approved)} 题交给批量编译复核"
                    f"（块大小 {audit_chunk}，单块上限 {config.AUDIT_TIMEOUT_S}s）…"
                )
                runner._compile_chunks(
                    approved,
                    work_prefix=f"{run_id}-final",
                    chunk_size=audit_chunk,
                    log_dir=config.RUNS_DIR,
                    source="final-audit",
                    timeout_s=config.AUDIT_TIMEOUT_S,
                    keep_on_timeout=True,
                )
                downgraded = sum(
                    1 for st in approved if st.status != "verified" and "audit_timeout" not in st.error_types
                )
                timed_out = sum(1 for st in approved if "audit_timeout" in st.error_types)
                ctx.log(f"[终审] 降级 {downgraded} 题；超时未判 {timed_out} 题（保留 worker 判定）")
    finally:
        if worker is not None:
            worker.stop()

    out = out_path or (config.RUNS_DIR / f"{run_id}.jsonl")
    model_name = model.name if model is not None else "none"
    runner._write_jsonl(out, [st.to_record(run_id=run_id, model_name=model_name) for st in states])
    return out, states
