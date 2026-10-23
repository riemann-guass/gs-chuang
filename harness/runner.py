"""证明回路与 JSONL 落盘。

两种模式：

* `run_cascade`  —— M1 的无模型基线。整套 tactic 级联写在一条 `first`
  表达式里，所有题拼成一个文件，一次编译。
* `run_llm_loop` —— M2 起。第 0 轮先跑级联，之后对未解决的题逐题问模型，
  每一轮把**当前所有未解决题**拼成一个文件再编译一次。

时间口径：批量编译的耗时无法分摊到单题，所以每题记 `time_ms` 为
「它参与的批次耗时之和」，并在记录里标注 `time_shared: true`——这是上界，
不是单题真实耗时。跑单题时用 `--no-batch`。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from . import config, diagnostics, leanenv, verify
from .cascade import cascade_proof
from .models import Attempt, ModelClient, ModelError, ProposeRequest
from .problems import Problem, family_of, statement_sha


@dataclass
class ProblemState:
    problem: Problem
    attempts: list[dict] = field(default_factory=list)
    status: str = "pending"
    proof: str | None = None
    axioms: tuple[str, ...] = ()
    error_types: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    time_ms: int = 0
    compile_rounds: int = 0
    #: 走过的阶段，例如 ["L0", "remedy", "L1#1"]
    stages: list[str] = field(default_factory=list)
    #: 单题墙钟的**估计值**：每参与一个批次，就累加「批次耗时 / 该批题数」。
    #: 比 `time_ms`（累加整个批次）更接近真实，但仍然是估计。
    wall_ms: float = 0.0

    def to_record(self, *, run_id: str, model_name: str) -> dict:
        return {
            "schema": 1,
            "run_id": run_id,
            "problem_id": self.problem.problem_id,
            "split": self.problem.split,
            "family": family_of(self.problem.problem_id),
            "status": self.status,
            "proof": self.proof,
            "attempts": self.attempts,
            "stages": self.stages,
            "time_ms": self.time_ms,
            "time_shared": True,
            "wall_ms": int(self.wall_ms),
            "wall_estimated": True,
            "compile_rounds": self.compile_rounds,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "model": model_name,
            "lean_toolchain": config.LEAN_TOOLCHAIN,
            "mathlib_rev": config.MATHLIB_REV,
            "ladder_version": config.LADDER_VERSION,
            # 单个声明的心跳上限会影响结果（太小会误杀慢证明），必须随记录保存
            "max_heartbeats": config.MAX_HEARTBEATS,
            "axioms": list(self.axioms),
            "error_types": self.error_types,
            "statement_sha256": statement_sha(self.problem),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


def _new_run_id(label: str) -> str:
    return f"{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _apply_audits(
    states: Sequence[ProblemState],
    *,
    batch: leanenv.RenderedBatch,
    result: leanenv.CompileResult,
    source: str,
) -> None:
    parsed = diagnostics.parse(result.output)
    per_problem = diagnostics.locate_spans(parsed.diagnostics, batch.spans)

    for st in states:
        pid = st.problem.problem_id
        if pid not in batch.spans:
            # 只提交了部分题（例如修复轮只编译未解决的题）时跳过其余题
            continue
        diags = per_problem.get(pid, [])
        report = verify.audit_problem(
            problem_id=pid,
            proof=st.attempts[-1]["proof"] if st.attempts else "",
            qualified_name=batch.qualified_names[pid],
            span_diagnostics=diags,
            axioms=parsed.axioms,
        )
        st.compile_rounds += 1
        st.time_ms += result.duration_ms
        # 单题墙钟估计：批次耗时按题数摊分（见 ADR-0003 对 time_ms 的说明）
        st.wall_ms += result.duration_ms / max(len(states), 1)
        st.attempts[-1]["status"] = report.status
        st.attempts[-1]["error_kind"] = report.error_kind
        st.attempts[-1]["diagnostics"] = "\n\n".join(d.text for d in diags)[:4000]
        st.attempts[-1]["compile_ms"] = result.duration_ms
        st.attempts[-1]["compile_shared"] = True
        if report.ok:
            st.status = "verified"
            st.proof = st.attempts[-1]["proof"]
            st.axioms = report.axioms
            # 失败类型只描述「当前状态」；补救轮成功之后，之前的失败原因不再适用
            st.error_types = []
        elif result.returncode == -1:
            # 整块编译超时被 harness 中止：这一题没有结论，不能算「证明失败」
            st.status = "error"
            if "batch_timeout" not in st.error_types:
                st.error_types.append("batch_timeout")
        elif report.error_kind == "none" and "no_axiom_report" in report.reasons and not diags:
            # 既没有诊断也没有公理报告：这一题根本没被 Lean 处理到。
            # 典型原因是同一批次里更靠前的某个声明把 Lean 进程带崩了。
            st.status = "error"
            if "batch_truncated" not in st.error_types:
                st.error_types.append("batch_truncated")
        else:
            st.status = "failed"
            if report.error_kind not in st.error_types:
                st.error_types.append(report.error_kind)


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _guard_split(problems: Sequence[Problem], *, allow_test: bool) -> None:
    if allow_test:
        return
    leaked = [p.problem_id for p in problems if p.split.lower() == "test"]
    if leaked:
        raise SystemExit(
            f"拒绝在未显式允许的情况下跑 Test 集（{len(leaked)} 题，例如 {leaked[:3]}）。"
            " 加 --allow-test 才放行。"
        )


def _compile_chunks(
    states: Sequence[ProblemState],
    *,
    work_prefix: str,
    chunk_size: int,
    log_dir: Path | None,
    source: str,
    extra_options: Sequence[str] = (),
    timeout_s: int | None = None,
) -> None:
    """把一批题按 `chunk_size` 切块编译。

    为什么必须切块：实测 244 题放进一个文件时，**第 111 题之后完全没有输出**——
    某个声明把 Lean 进程带崩，后面的题根本没被处理，却会被误判成「证明失败」。
    切块把爆炸半径限制在一块之内，并且能定位是哪一块出的问题。
    """
    states = list(states)
    size = chunk_size if chunk_size and chunk_size > 0 else len(states)
    for ci in range(0, len(states), size):
        chunk = states[ci : ci + size]
        items = [st.problem.item(st.attempts[-1]["proof"]) for st in chunk]
        batch, result = leanenv.compile_items(
            items,
            work_name=f"{work_prefix}-c{ci // size:02d}",
            log_dir=log_dir,
            extra_options=extra_options,
            timeout_s=timeout_s,
        )
        _apply_audits(chunk, batch=batch, result=result, source=source)


def run_cascade(
    problems: Sequence[Problem],
    *,
    out_path: Path | None = None,
    label: str = "m1-cascade",
    allow_test: bool = False,
    deep: bool = False,
    chunk_size: int = 0,
    extra_options: Sequence[str] = (),
    remediate: bool = False,
) -> tuple[Path, list[ProblemState]]:
    config.ensure_dirs()
    _guard_split(problems, allow_test=allow_test)
    run_id = _new_run_id(label)

    states = [ProblemState(problem=p) for p in problems]
    proof = cascade_proof(deep=deep)
    for st in states:
        st.attempts.append({"round": 0, "source": "cascade", "proof": proof})

    _compile_chunks(
        states,
        work_prefix=f"{run_id}-r0",
        chunk_size=chunk_size,
        log_dir=config.RUNS_DIR,
        source="cascade",
        extra_options=extra_options,
    )

    if remediate:
        # 第二遍：只对「因限制类 option 失败」的题，用同一套 tactic + 提高限制重跑。
        # 不需要模型、零 token，见 docs/research/m3-deterministic-remediation.md。
        candidates = [
            st
            for st in states
            if st.status != "verified" and (config.REMEDY_TRIGGERS & set(st.error_types))
        ]
        if candidates:
            print(
                f"[补救] {len(candidates)} 道题触发（{sorted(config.REMEDY_TRIGGERS)}），"
                f"options={list(config.REMEDY_OPTIONS)}",
                flush=True,
            )
            for st in candidates:
                st.attempts.append(
                    {
                        "round": 1,
                        "source": "cascade-remedy",
                        "proof": proof,
                        "extra_options": list(config.REMEDY_OPTIONS),
                    }
                )
            _compile_chunks(
                candidates,
                work_prefix=f"{run_id}-remedy",
                chunk_size=chunk_size,
                log_dir=config.RUNS_DIR,
                source="cascade-remedy",
                extra_options=config.REMEDY_OPTIONS,
                timeout_s=config.REMEDY_TIMEOUT_S,
            )
        else:
            print("[补救] 没有题需要补救", flush=True)

    out = out_path or (config.RUNS_DIR / f"{run_id}.jsonl")
    _write_jsonl(out, [st.to_record(run_id=run_id, model_name="none") for st in states])
    return out, states


def run_llm_loop(
    problems: Sequence[Problem],
    model: ModelClient,
    *,
    rounds: int = 6,
    out_path: Path | None = None,
    label: str = "m2-llm",
    allow_test: bool = False,
    with_cascade: bool = True,
    deep: bool = False,
    chunk_size: int = 0,
    use_hints: bool = False,
) -> tuple[Path, list[ProblemState]]:
    config.ensure_dirs()
    _guard_split(problems, allow_test=allow_test)
    run_id = _new_run_id(label)
    states = [ProblemState(problem=p) for p in problems]

    if with_cascade:
        proof0 = cascade_proof(deep=deep)
        for st in states:
            st.attempts.append({"round": 0, "source": "cascade", "proof": proof0})
        _compile_chunks(
            states,
            work_prefix=f"{run_id}-r0",
            chunk_size=chunk_size,
            log_dir=config.RUNS_DIR,
            source="cascade",
        )

    for rnd in range(1, rounds + 1):
        pending = [st for st in states if st.status != "verified"]
        if not pending:
            break
        prepared: list[ProblemState] = []
        api_errors = 0
        for st in pending:
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
                        hints=use_hints,
                    )
                )
            except ModelError as exc:
                # 单题模型调用失败不能让整轮崩掉：记一条失败尝试，继续下一题。
                api_errors += 1
                st.attempts.append(
                    {
                        "round": rnd,
                        "source": model.name,
                        "proof": "",
                        "status": "error",
                        "error_kind": f"api_error:{exc.kind}",
                        "diagnostics": exc.detail[:2000],
                        "tokens_in": 0,
                        "tokens_out": 0,
                    }
                )
                st.status = "error"
                kind = f"api_error:{exc.kind}"
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
            prepared.append(st)

        if not prepared:
            # 整轮全部调用失败：再跑下去没有意义，直接结束并保留已记录的错误。
            print(f"[warn] 第 {rnd} 轮全部 {api_errors} 次模型调用失败，提前结束", flush=True)
            break

        _compile_chunks(
            prepared,
            work_prefix=f"{run_id}-r{rnd}",
            chunk_size=chunk_size,
            log_dir=config.RUNS_DIR,
            source=model.name,
        )

    out = out_path or (config.RUNS_DIR / f"{run_id}.jsonl")
    _write_jsonl(out, [st.to_record(run_id=run_id, model_name=model.name) for st in states])
    return out, states
