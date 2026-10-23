"""把 Lean 诊断里的 goal state 解析成结构化目标。

**这一步只做地基，不接进 prompt。** 调研报告 §5.2 的结论是「结构化 goal state 是
关键增量」，但没有真实模型数据时无法判断增益来源，所以先只把解析器写好、测好，
等 M2 的真实数据到手再接（见 `docs/research/m2-smoke.md`）。

输入是 `Diagnostic.detail`，实测有两种形态：

1. 级联哨兵（`fail "cascade_exhausted"`）——单目标、没有 `unsolved goals` 标记：

```
cascade_exhausted
x : ℝ
h₀ : x ^ 2 - 5 * x - 4 ≤ 10
⊢ x ≥ -2 ∧ x ≤ 7
```

2. `aesop` 等多目标失败——带 `unsolved goals` 与 `case` 分支：

```
aesop: failed to prove the goal after exhaustive search.

unsolved goals
case left
x : ℝ
h₀ : x ^ 2 ≤ 10 + 4 + 5 * x
⊢ -2 ≤ x
case right
x : ℝ
h₀ : x ^ 2 ≤ 10 + 4 + 5 * x
⊢ x ≤ 7
```

解析失败时返回空列表，**不抛异常**——诊断文本是外部输入，不能让它搞崩回路。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TURNSTILE = "⊢"
_CASE_RE = re.compile(r"^case\s+(?P<name>\S+)\s*$")
_UNSOLVED = "unsolved goals"


@dataclass
class Goal:
    name: str | None
    hypotheses: list[str] = field(default_factory=list)
    target: str = ""

    def render(self) -> str:
        lines = [f"case {self.name}"] if self.name else []
        lines.extend(self.hypotheses)
        lines.append(f"⊢ {self.target}")
        return "\n".join(lines)


def _split_cases(body: str) -> list[tuple[str | None, list[str]]]:
    """按 `case xxx` 切段；没有 case 时整段作为一个无名目标。"""
    segments: list[tuple[str | None, list[str]]] = []
    name: str | None = None
    buf: list[str] = []
    seen_case = False

    for raw in body.split("\n"):
        line = raw.rstrip()
        m = _CASE_RE.match(line.strip())
        if m:
            if buf:
                segments.append((name, buf))
            name = m.group("name")
            buf = []
            seen_case = True
            continue
        buf.append(line)
    if buf:
        segments.append((name, buf))
    if not seen_case and segments:
        name, buf = segments[0]
        return [(None, buf)]
    return segments


def _parse_segment(name: str | None, lines: list[str]) -> Goal | None:
    hyps: list[str] = []
    target_lines: list[str] = []
    in_target = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_TURNSTILE):
            in_target = True
            target_lines.append(stripped[len(_TURNSTILE):].strip())
            continue
        if in_target:
            target_lines.append(stripped)
            continue
        # 目标之前：判断是新的假设还是上一条假设的续行。
        # 判据用「这一行有没有 `:`」而不是 `^\S+\s*:`——像 `x y z a b : ℝ`
        # 这种多变量绑定，正则会把 `x` 之后的空格误判成续行。
        if hyps and ":" not in stripped:
            hyps[-1] = f"{hyps[-1]} {stripped}"
        else:
            hyps.append(stripped)

    target = " ".join(t for t in target_lines if t).strip()
    if not target:
        return None

    # 过滤掉不含 ':' 的噪声行（例如哨兵消息 `cascade_exhausted`）
    clean = [h for h in hyps if ":" in h]
    return Goal(name=name, hypotheses=clean, target=target)


def parse_goals(detail: str) -> list[Goal]:
    """从诊断细节里解析出目标列表；解析不出来就返回 `[]`。"""
    if not detail or _TURNSTILE not in detail:
        return []

    text = detail.replace("\r\n", "\n").replace("\r", "\n")
    marker = text.find(_UNSOLVED)
    body = text[marker + len(_UNSOLVED):] if marker >= 0 else text

    goals: list[Goal] = []
    for name, lines in _split_cases(body):
        g = _parse_segment(name, lines)
        if g is not None:
            goals.append(g)
    return goals


def parse_goals_from_diagnostics(diagnostics) -> list[Goal]:
    """对一批 `Diagnostic` 逐个解析，合并去重。"""
    out: list[Goal] = []
    seen: set[str] = set()
    for d in diagnostics:
        for g in parse_goals(d.detail):
            key = g.render()
            if key not in seen:
                seen.add(key)
                out.append(g)
    return out


def render_goals(goals: list[Goal]) -> str:
    """渲染回可读文本（给 prompt 用的稳定格式）。"""
    if not goals:
        return "(无可用 goal state)"
    return "\n\n".join(g.render() for g in goals)
