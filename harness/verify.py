"""判定「证明成功」的四项审计。

一条记录只有同时满足下面四条才算 `verified`：

1. 编译期在该题 span 内没有 `error`；
2. `#print axioms` 里没有 `sorryAx`（同时覆盖显式 `sorry` 与 elaboration 失败）；
3. 公理集合 ⊆ `{propext, Classical.choice, Quot.sound}`；
4. 证明文本里没有禁用 token（`sorry` / `admit` / `native_decide` / `axiom` / `unsafe`）。

注意：**不能**用进程退出码判定单题成败。批量文件里只要有一道题失败，
`lake env lean` 就返回 1，但同文件里其它题可能都证完了。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config
from .diagnostics import AxiomReport, Diagnostic, classify

_TOKEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in config.FORBIDDEN_TOKENS) + r")\b"
)


@dataclass
class AuditReport:
    problem_id: str
    status: str  # "verified" | "failed"
    reasons: list[str] = field(default_factory=list)
    axioms: tuple[str, ...] = ()
    error_kind: str = "none"
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "verified"


def forbidden_tokens(proof: str) -> list[str]:
    return sorted({m.group(1) for m in _TOKEN_RE.finditer(proof)})


def audit_problem(
    *,
    problem_id: str,
    proof: str,
    qualified_name: str,
    span_diagnostics: list[Diagnostic],
    axioms: dict[str, AxiomReport],
) -> AuditReport:
    reasons: list[str] = []
    errors = [d for d in span_diagnostics if d.severity == "error"]
    warnings = [d for d in span_diagnostics if d.severity == "warning"]

    bad = forbidden_tokens(proof)
    if bad:
        reasons.append(f"forbidden_token:{','.join(bad)}")

    if errors:
        reasons.append(f"compile_error:{classify(errors)}")

    report = axioms.get(qualified_name)
    if report is None:
        # 定理没有进入环境（通常是 elaboration 失败），拿不到公理报告
        reasons.append("no_axiom_report")
        ax: tuple[str, ...] = ()
    else:
        ax = report.axioms
        if report.uses_sorry:
            reasons.append("sorry_ax")
        extra = set(ax) - config.ALLOWED_AXIOMS
        if extra:
            reasons.append(f"axiom_not_allowed:{','.join(sorted(extra))}")

    for w in warnings:
        if "declaration uses" in w.message and "sorry" in w.message:
            if "sorry_ax" not in reasons:
                reasons.append("sorry_warning")

    # 没有 error、没有 sorryAx、公理干净 —— 才算证完
    status = "verified" if not reasons else "failed"
    kind = classify(errors) if errors else ("sorry" if any("sorry" in r for r in reasons) else "none")
    return AuditReport(
        problem_id=problem_id,
        status=status,
        reasons=reasons,
        axioms=ax,
        error_kind=kind,
        diagnostics=span_diagnostics,
    )
