"""引擎对外接口。

这是 App / CLI / 评测**唯一**应该调用的入口。目标是把「跑一批题」的实验脚本
变成「给定定理，返回经过 kernel 验证的证明」的引擎。

## 两种用法，别用错

```python
# 批量（正常路径）：一次 Mathlib 载入，N 道题摊分
results = prove_many(problems, budget=Budget(), model=client)

# 单题（调试/演示）：每次都要付约 240 s 的 Mathlib 载入
r = prove("theorem foo (n : Nat) : n + 0 = n")
```

**单题接口目前慢到不能做交互**，这是已知限制，不是 bug。根因是 Lean 侧的
`import Mathlib` 一次性载入约 240 s（见 `docs/decisions/ADR-0001`）。
低延迟要靠常驻 Lean 会话（v0.2）解决，不在这版范围。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import config, metrics, pipeline, runner
from .models import ModelClient, build_model
from .problems import Problem, load_index


@dataclass(frozen=True)
class Budget:
    """单次证明尝试的预算。

    `max_rounds` 会被阶段机强制执行；`max_tokens` 逐题拦截；
    `max_wall_s` 到点后不再开新的 L1 轮（已开始的轮会跑完）。
    """

    max_rounds: int = 2
    max_tokens: int = 20_000
    max_wall_s: float = 0.0
    remediate: bool = True
    chunk_size: int = 60


@dataclass
class ProofResult:
    problem_id: str
    status: str  # verified | failed | timeout | error
    proof: str | None = None
    stages: list[str] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    axioms: list[str] = field(default_factory=list)
    wall_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_cny: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == "verified"

    @classmethod
    def from_state(cls, st: runner.ProblemState) -> "ProofResult":
        return cls(
            problem_id=st.problem.problem_id,
            status=st.status,
            proof=st.proof,
            stages=list(st.stages),
            attempts=list(st.attempts),
            axioms=list(st.axioms),
            wall_ms=int(st.wall_ms),
            tokens_in=st.tokens_in,
            tokens_out=st.tokens_out,
            cost_cny=config.token_cost_cny(st.tokens_in, st.tokens_out),
        )


def problem_from_statement(statement: str, *, problem_id: str | None = None) -> Problem:
    """把一条 Lean 定理语句包成 `Problem`。

    语句必须自带 `theorem <name>`，例如
    `theorem foo (n : Nat) : n + 0 = n`。
    """
    text = statement.strip()
    if not text.startswith("theorem "):
        raise ValueError("语句必须以 `theorem ` 开头（本版不做自然语言自动形式化）")
    name = text.split()[1].split("(")[0].strip()
    return Problem(
        problem_id=problem_id or name,
        split="Adhoc",
        header=text,
        body="",
    )


def prove(
    problem: Problem | str,
    *,
    budget: Budget = Budget(),
    client: ModelClient | None = None,
    allow_network: bool = True,
) -> ProofResult:
    """证明**一道题**。

    警告：每次调用都会重新载入 Mathlib（约 240 s）。批量请用 `prove_many`。
    """
    p = problem_from_statement(problem) if isinstance(problem, str) else problem
    results = prove_many([p], budget=budget, client=client, allow_network=allow_network, label="prove")
    return results[0]


def prove_many(
    problems: list[Problem],
    *,
    budget: Budget = Budget(),
    client: ModelClient | None = None,
    allow_network: bool = True,
    label: str = "prove-many",
    out_path: Path | None = None,
) -> list[ProofResult]:
    """批量证明。这是正常路径：一次编译摊分多道题。"""
    model = client
    if model is None and budget.max_rounds > 0:
        model, _note = build_model(allow_network=allow_network)

    out, states = pipeline.run_pipeline(
        problems,
        model=model,
        rounds=budget.max_rounds,
        remediate=budget.remediate,
        chunk_size=budget.chunk_size,
        max_tokens=budget.max_tokens,
        max_wall_s=budget.max_wall_s,
        label=label,
        allow_test=False,
        out_path=out_path,
    )
    _ = out
    return [ProofResult.from_state(st) for st in states]


def prove_dataset(
    *,
    select: str = "easy",
    split: str = "Valid",
    limit: int | None = None,
    budget: Budget = Budget(),
    client: ModelClient | None = None,
    allow_network: bool = True,
    label: str = "dataset",
    out_path: Path | None = None,
) -> tuple[Path, list[ProofResult], dict]:
    """在一批 bench 题上跑完整流程，返回 (记录路径, 结果, 汇总)。"""
    from .cli import select_problems

    problems = select_problems(load_index(), select, limit, split=split)
    model = client
    if model is None and budget.max_rounds > 0:
        model, _note = build_model(allow_network=allow_network)
    out, states = pipeline.run_pipeline(
        problems,
        model=model,
        rounds=budget.max_rounds,
        remediate=budget.remediate,
        chunk_size=budget.chunk_size,
        max_tokens=budget.max_tokens,
        max_wall_s=budget.max_wall_s,
        label=label,
        out_path=out_path,
    )
    results = [ProofResult.from_state(st) for st in states]
    summary = metrics.summarize(metrics.load_jsonl(out))
    return out, results, summary.as_dict()
