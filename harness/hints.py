"""把 Lean 的失败诊断映射成**具体对策**，供 prompt 使用。

## 为什么先做这个，而不是 goal state 结构化

M2（`docs/research/m2-result.md`）里最漂亮的一条证据：`mathd_numbertheory_198`
在第 0 轮报的是 `max_rec_depth`，模型第 1 轮直接给出

```lean
set_option maxRecDepth 10000 in
set_option exponentiation.threshold 10000 in
norm_num
```

也就是说它**看懂了诊断，并且知道对应的开关**。这类映射成本极低（一张表 + 一段 prompt），
而 goal state 结构化需要改协议、改解析、还要重跑对照。先试便宜的。

## 注意

这些提示是**假设**，不是结论。它们的效果必须在同一批题上做 A/B 才能确认，
所以默认**不注入** prompt（`--hints` 才开）。见 ADR-0006。
"""

from __future__ import annotations

from typing import Iterable

#: 诊断类型 → 建议。键与 `harness.diagnostics.classify()` 的返回值一致。
COUNTERMEASURES: dict[str, tuple[str, ...]] = {
    "max_rec_depth": (
        "Lean hit its recursion-depth limit (maxRecDepth, default 1000). "
        "Prepend `set_option maxRecDepth 10000 in` to the tactic.",
        "If the goal has a huge exponent, also prepend "
        "`set_option exponentiation.threshold 10000 in`.",
    ),
    "cascade_exhausted": (
        "No single cheap tactic closed the goal. Try: `simp_all`, `nlinarith`, "
        "`positivity`, or split the goal first (`constructor`, `by_cases h : P`, "
        "`interval_cases n`).",
        "If the goal is an existential or conjunction, consider proving it by "
        "`refine ⟨?_, ?_⟩` and closing the pieces separately.",
    ),
    "unsolved_goals": (
        "The tactic ran but left goals. Look at the remaining goal and target it "
        "directly, e.g. `have h : <key fact> := by ...` then `rw`/`exact`.",
        "`omega` for linear integer goals, `linarith` for linear real goals, "
        "`ring`/`ring_nf` for ring identities.",
    ),
    "unknown_identifier": (
        "A name was not found. Do not invent Mathlib names — use `exact?` or "
        "`apply?` to search, or restate without the missing lemma.",
    ),
    "type_mismatch": (
        "Check coercions between ℕ / ℤ / ℝ. `norm_cast`, `push_cast`, or an "
        "explicit `(h : (n : ℤ) = 0)` cast often fixes it.",
    ),
    "tactic_error": (
        "The tactic was applied to the wrong shape of goal. Inspect the goal "
        "first (`case`/`⊢` line) and pick a tactic that matches its head symbol.",
    ),
    "syntax_error": (
        "The output did not parse. Emit only tactic code, one tactic per line, "
        "and do not repeat the theorem statement.",
    ),
    "arithmetic_unclosed": (
        "`linarith` found no contradiction. Try `nlinarith` with explicit "
        "nonnegativity hints, or provide an intermediate equality.",
    ),
    "exponent_threshold": (
        "Lean refused to evaluate a large exponent. Prepend "
        "`set_option exponentiation.threshold 10000 in`.",
    ),
    "other": (
        "Read the message and the goal state literally; do not guess.",
    ),
}

_GENERIC = (
    "Read the goal state in the diagnostics and answer with tactics only.",
)


def hints_for(kinds: Iterable[str]) -> list[str]:
    """按诊断类型取建议（去重、保序）。"""
    out: list[str] = []
    for kind in kinds:
        for h in COUNTERMEASURES.get(kind, ()):
            if h not in out:
                out.append(h)
    if not out:
        out.append(_GENERIC)
    return out


def render_hints(kinds: Iterable[str]) -> str:
    hints = hints_for(kinds)
    return "\n".join(f"- {h}" for h in hints)


def kinds_from_diagnostics(diagnostics) -> list[str]:
    """从一批 `Diagnostic` 里取出去重后的类型（跳过无信息的 `none` / `other`）。"""
    from .diagnostics import classify

    out: list[str] = []
    for d in diagnostics:
        k = classify([d])
        if k not in {"none", "other"} and k not in out:
            out.append(k)
    return out
