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
    """L1：逐题问模型要 tactics，再把所有候选拼成一批编译。"""
    rnd = ctx.next_round()
    prepared: list[runner.ProblemState] = []
    api_errors = 0

    for st in states:
        history = [
            Attempt(
                source=a["source"],
                proof=a["proof"],
                status=a.get("status", "unknown"),
                error_kind=a.get("error_kind", "none"),
                diagnostics=a.get("diagnostics", ""),
            )
            for a in st.attempts
        ]
        try:
            resp = model.propose(
                ProposeRequest(
                    problem=st.problem,
                    attempt_index=rnd - 1,
                    history=history,
                    hints=ctx.use_hints,
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

        st.status = "failed" if st.status == "error" else st.status
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
        ctx.log(f"[{ctx.judge_name}] 第 {rnd} 轮：{accepted}/{len(prepared)} 通过（待终审）")
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


# --------------------------------------------------------------------- stages
@dataclass(frozen=True)
class Stage:
    name: str
    #: 触发条件：空集 = 所有未解决题；否则要求 error_types 与本集合有交集
    triggers: frozenset[str] = frozenset()
    repeat: int = 1
    #: 自定义实现（测试或未来的 L2/L3 用）；为空时按 name 分派到内置阶段
    fn: Callable[[list[runner.ProblemState], Context], None] | None = None


def pipeline_v1(*, rounds: int, remediate: bool) -> list[Stage]:
    stages = [Stage("L0")]
    if remediate:
        stages.append(Stage("remedy", triggers=config.REMEDY_TRIGGERS))
    stages.append(Stage("L1", repeat=max(rounds, 0)))
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
    )

    worker = None
    if judge == "worker":
        from .worker import LeanWorker, binder_count, statement_type

        worker = LeanWorker()
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
                worker = LeanWorker()
                worker.start()
                st.attempts[-1]["error_kind"] = "worker_crash"
                st.attempts[-1]["diagnostics"] = str(exc)[:500]
                return False
            # 把判定与诊断写回 attempt：下一轮拼 history 时模型就能看到反馈
            st.attempts[-1]["error_kind"] = r.reason
            st.attempts[-1]["diagnostics"] = r.error[:1000]
            st.attempts[-1]["status"] = "verified" if r.ok else "failed"
            return r.ok

        ctx.judge = _judge
        ctx.judge_name = "worker"

    try:
        states = [runner.ProblemState(problem=p) for p in problems]
        plan = stages if stages is not None else pipeline_v1(rounds=rounds, remediate=remediate)

        for stage in plan:
            for _ in range(stage.repeat):
                pending = [st for st in states if st.status != "verified"]
                if not pending:
                    break
                if stage.triggers:
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
                else:
                    raise ValueError(f"未知阶段：{stage.name}")

        # 终审：worker 放行的证明仍要走一遍批量编译 + 四项审计
        if worker is not None:
            approved = [st for st in states if st.status == "verified"]
            if approved:
                ctx.log(f"[终审] {len(approved)} 题交给批量编译复核…")
                runner._compile_chunks(
                    approved,
                    work_prefix=f"{run_id}-final",
                    chunk_size=chunk_size,
                    log_dir=config.RUNS_DIR,
                    source="final-audit",
                )
                downgraded = sum(1 for st in approved if st.status != "verified")
                ctx.log(f"[终审] 降级 {downgraded} 题")
    finally:
        if worker is not None:
            worker.stop()

    out = out_path or (config.RUNS_DIR / f"{run_id}.jsonl")
    model_name = model.name if model is not None else "none"
    runner._write_jsonl(out, [st.to_record(run_id=run_id, model_name=model_name) for st in states])
    return out, states
