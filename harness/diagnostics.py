"""解析 Lean 编译器输出。

输出形态（实测，Windows、`lake env lean`）：

```
'Ns.t1_ok' depends on axioms: [propext, Classical.choice, Quot.sound]
D:\\...\\batch.lean:15:2: error: linarith failed to find a contradiction
x : ℝ
h : x ^ 2 - 5 * x - 4 ≤ 10
⊢ False
failed
'Ns.t3_sorry' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
D:\\...\\batch.lean:19:8: warning: declaration uses `sorry`
'Ns.t4_after' does not depend on any axioms
```

要点：

* 诊断行以 `路径:行:列: 级别: 消息` 开头；**后续行是 goal state 等细节**，
  要归到该诊断上，而不是丢掉。
* `#print axioms` 的输出没有 `路径:行:列` 前缀，必须优先匹配，
  否则会被误当作上一条错误的细节。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .leanenv import Span

# 路径里可能含 Windows 盘符冒号，所以文件部分用 .*? 且要求后面紧跟 :数字:数字:
_DIAG_RE = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s*(?P<sev>error|warning|info):\s*(?P<msg>.*)$"
)
#: 公理输出的起始行；`rest` 可能不带闭合 `]`（定理名太长时 Lean 会折行）
_AXIOM_START_RE = re.compile(r"^'(?P<name>.+?)' depends on axioms: \[(?P<rest>.*)$")
_AXIOM_NONE_RE = re.compile(r"^'(?P<name>.+?)' does not depend on any axioms\s*$")


@dataclass
class Diagnostic:
    severity: str
    message: str
    file: str
    line: int
    col: int
    detail: str = ""

    @property
    def text(self) -> str:
        return f"{self.message}\n{self.detail}".strip() if self.detail else self.message


@dataclass
class AxiomReport:
    name: str
    axioms: tuple[str, ...]

    @property
    def uses_sorry(self) -> bool:
        return "sorryAx" in self.axioms


@dataclass
class ParsedOutput:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    axioms: dict[str, AxiomReport] = field(default_factory=dict)
    unparsed: list[str] = field(default_factory=list)

    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]


def _clean_axiom_token(token: str) -> str:
    return token.strip().strip("[]").strip()


def _absorb_axiom(
    parsed: ParsedOutput, name: str, tokens: list[str], *, closed: bool
) -> tuple[str, list[str]] | None:
    """闭合则记录；否则返回待续状态，由后续行补齐。"""
    if not closed:
        return (name, tokens)
    axioms = tuple(a for a in (_clean_axiom_token(t) for t in tokens) if a)
    parsed.axioms[name] = AxiomReport(name=name, axioms=axioms)
    return None


def parse(output: str) -> ParsedOutput:
    """把编译器输出切成结构化诊断与公理审计。

    **注意换行**：定理名很长时，`#print axioms` 的输出会被 Lean 按终端宽度折行：

    ```
    'M0019.algebra_3rootspoly_amdtamc...' depends on axioms: [propext,
     Classical.choice,
     Quot.sound]]
    ```

    早期版本要求整条在一行，导致这类题拿不到公理报告，被误判成 `batch_truncated`。
    """
    parsed = ParsedOutput()
    current: Diagnostic | None = None
    pending: tuple[str, list[str]] | None = None

    for raw in output.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()

        # 1) 正在拼接被折行的公理输出
        if pending is not None:
            name, tokens = pending
            closed = "]" in line
            head = line.split("]", 1)[0]
            tokens.extend(t for t in head.split(",") if t.strip())
            if closed:
                _absorb_axiom(parsed, name, tokens, closed=True)
                pending = None
            else:
                pending = (name, tokens)
            continue

        # 2) 公理输出的起始行
        m = _AXIOM_START_RE.match(line)
        if m:
            rest = m.group("rest")
            tokens = [t for t in rest.split("]")[0].split(",") if t.strip()]
            pending = _absorb_axiom(parsed, m.group("name"), tokens, closed="]" in rest)
            current = None
            continue

        m = _AXIOM_NONE_RE.match(line)
        if m:
            parsed.axioms[m.group("name")] = AxiomReport(name=m.group("name"), axioms=())
            current = None
            continue

        m = _DIAG_RE.match(line)
        if m:
            current = Diagnostic(
                severity=m.group("sev"),
                message=m.group("msg"),
                file=m.group("file"),
                line=int(m.group("line")),
                col=int(m.group("col")),
            )
            parsed.diagnostics.append(current)
            continue

        if not line.strip():
            continue

        if current is not None:
            current.detail = (current.detail + "\n" + line).strip()
        else:
            parsed.unparsed.append(line)

    return parsed


def locate_spans(
    diagnostics: Iterable[Diagnostic], spans: Mapping[str, Span]
) -> dict[str, list[Diagnostic]]:
    """把诊断按行号映射回题目。落在任何 span 之外的诊断被丢弃。"""
    out: dict[str, list[Diagnostic]] = {pid: [] for pid in spans}
    ordered = sorted(spans.items(), key=lambda kv: kv[1].first_line)
    for d in diagnostics:
        for pid, span in ordered:
            if span.first_line <= d.line <= span.last_line:
                out[pid].append(d)
                break
    return out


def classify(diagnostics: Iterable[Diagnostic]) -> str:
    """给一组诊断打一个粗粒度失败类型，用于统计。"""
    joined = "\n".join(d.message for d in diagnostics).lower()
    if not joined:
        return "none"
    # 级联哨兵：所有 tactic 分支都没能闭合目标
    if "cascade_exhausted" in joined:
        return "cascade_exhausted"
    if "failed to find a contradiction" in joined or "linarith" in joined:
        return "arithmetic_unclosed"
    if "unsolved goals" in joined:
        return "unsolved_goals"
    if "unknown identifier" in joined or "unknown constant" in joined:
        return "unknown_identifier"
    if "type mismatch" in joined or "application type mismatch" in joined:
        return "type_mismatch"
    # Lean 的递归深度上限：大数字上的 simp/decide 常见死法
    if "maximum recursion depth" in joined:
        return "max_rec_depth"
    if "exceeds the threshold" in joined and "exponent" in joined:
        return "exponent_threshold"
    # `first | ... | ...` 所有分支都失败时，Lean 报的是最后一个 tactic 的失败信息
    if "failed, made no progress" in joined or "failed to prove the goal" in joined:
        return "cascade_exhausted"
    if "does not evaluate to a proof" in joined or "tactic" in joined:
        return "tactic_error"
    if "syntax error" in joined or "unexpected" in joined or "unexpected token" in joined:
        return "syntax_error"
    return "other"
