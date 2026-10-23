"""goal state 解析的单测。

fixture 全部来自 2026-10-19 的真实运行记录（`runs/m1-l0.jsonl`）与当时的
`aesop` 失败输出，不是手写的理想格式。
"""

from __future__ import annotations

from harness.goals import Goal, parse_goals, parse_goals_from_diagnostics, render_goals

# 来自 runs/m1-l0.jsonl：mathd_algebra_101（级联哨兵，单目标，无 unsolved goals 标记）
SENTINEL_SINGLE = """cascade_exhausted
x : ℝ
h₀ : x ^ 2 - 5 * x - 4 ≤ 10
⊢ x ≥ -2 ∧ x ≤ 7"""

# 来自 runs/m1-l0.jsonl：imo_1961_p1（级联哨兵，多假设）
SENTINEL_MANY_HYPS = """cascade_exhausted
x y z a b : ℝ
h₀ : 0 < x ∧ 0 < y ∧ 0 < z
h₁ : x ≠ y
h₂ : y ≠ z
h₃ : z ≠ x
h₄ : x + y + z = a
h₅ : x ^ 2 + y ^ 2 + z ^ 2 = b ^ 2
h₆ : x * y = z ^ 2
⊢ 0 < a ∧ b ^ 2 < a ^ 2 ∧ a ^ 2 < 3 * b ^ 2"""

# 来自早一轮的 aesop 失败：带 unsolved goals 与两个 case
AESOP_MULTI = """aesop: failed to prove the goal after exhaustive search.

unsolved goals
case left
x : ℝ
h₀ : x ^ 2 ≤ 10 + 4 + 5 * x
⊢ -2 ≤ x
case right
x : ℝ
h₀ : x ^ 2 ≤ 10 + 4 + 5 * x
⊢ x ≤ 7"""


def test_parse_sentinel_single_goal():
    goals = parse_goals(SENTINEL_SINGLE)
    assert len(goals) == 1
    g = goals[0]
    assert g.name is None
    assert g.target == "x ≥ -2 ∧ x ≤ 7"
    assert any(h.startswith("h₀") for h in g.hypotheses)
    # 哨兵消息不含 ':'，必须被过滤掉，不能混进假设
    assert all("cascade_exhausted" not in h for h in g.hypotheses)


def test_parse_sentinel_many_hypotheses():
    g = parse_goals(SENTINEL_MANY_HYPS)[0]
    # 1 行变量绑定 + h₀..h₆ 共 7 条假设
    assert len(g.hypotheses) == 8
    assert g.hypotheses[0] == "x y z a b : ℝ"
    assert g.hypotheses[1].startswith("h₀")
    assert g.hypotheses[-1].startswith("h₆")
    assert g.target.startswith("0 < a")


def test_parse_aesop_multiple_cases():
    goals = parse_goals(AESOP_MULTI)
    assert len(goals) == 2
    assert [g.name for g in goals] == ["left", "right"]
    assert goals[0].target == "-2 ≤ x"
    assert goals[1].target == "x ≤ 7"


def test_parse_empty_and_garbage_returns_empty():
    assert parse_goals("") == []
    assert parse_goals("cascade_exhausted") == []
    assert parse_goals("just some error text\nwith ⊢ but no goal?") == []


def test_render_roundtrip():
    goals = parse_goals(AESOP_MULTI)
    text = render_goals(goals)
    assert "case left" in text and "⊢ -2 ≤ x" in text
    # 渲染结果再解析应得到同样的目标
    again = parse_goals(text)
    assert [g.target for g in again] == [g.target for g in goals]


def test_parse_from_diagnostics_dedup():
    from harness.diagnostics import Diagnostic

    d1 = Diagnostic(severity="error", message="cascade_exhausted", file="x", line=1, col=1, detail=SENTINEL_SINGLE)
    d2 = Diagnostic(severity="error", message="cascade_exhausted", file="x", line=9, col=1, detail=SENTINEL_SINGLE)
    goals = parse_goals_from_diagnostics([d1, d2])
    assert len(goals) == 1


def test_render_when_empty():
    assert render_goals([]) == "(无可用 goal state)"


def test_goal_dataclass_render():
    g = Goal(name="left", hypotheses=["x : ℝ"], target="x = x")
    assert g.render() == "case left\nx : ℝ\n⊢ x = x"
