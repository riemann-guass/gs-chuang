"""`harness/roles.py` 的离线单测：闭集收敛、解析容错、prompt 内容。

不起 Lean、不联网。
"""

from __future__ import annotations

import pytest

from harness import roles


@pytest.mark.parametrize(
    "raw, want",
    [
        ("wrong_strategy", "wrong_strategy"),
        ("Wrong-Strategy: 应该反证", "wrong_strategy"),
        ("syntax_error", "syntax"),
        ("unknown_lemma: 缺 Nat.dvd 引理", "missing_lemma"),
        ("induction", "needs_induction"),
        ("unsolved_goals", "unsolved"),
        ("something_weird", "other"),
        ("", "other"),
    ],
)
def test_normalize_label(raw, want):
    assert roles.normalize_label(raw) == want


@pytest.mark.parametrize(
    "text, label, note_contains",
    [
        ("wrong_strategy: 该反证却直证", "wrong_strategy", "反证"),
        ("syntax_error: 拼写错", "syntax", "拼写"),
        ("  type_mismatch : n 是 ℕ 不是 ℤ  ", "type_mismatch", "ℕ"),
        ("我觉得应该用归纳法", "other", "归纳"),  # 没按格式 → other，但保留原文摘要
        ("", "other", ""),
    ],
)
def test_parse_critic(text, label, note_contains):
    got_label, note = roles.parse_critic(text)
    assert got_label == label
    assert note_contains in note


def test_parse_critic_multiline_uses_first_line():
    label, _ = roles.parse_critic("wrong_strategy: 方向错\n这里还有多余解释")
    assert label == "wrong_strategy"


@pytest.mark.parametrize(
    "text, strategy_head, sketch_contains",
    [
        ("STRATEGY: 对 n 归纳\nSKETCH: step 用 simp [ih]", "对 n 归纳", "simp [ih]"),
        ("strategy: 反证\nsketch:", "反证", ""),
        ("先反证再用 nlinarith", "先反证", ""),  # 未按格式 → 首行当策略
    ],
)
def test_parse_strategist(text, strategy_head, sketch_contains):
    strategy, sketch = roles.parse_strategist(text)
    assert strategy.startswith(strategy_head)
    assert sketch_contains in sketch


def test_parse_strategist_empty():
    assert roles.parse_strategist("") == ("", "")


def test_prompts_include_header_and_clip():
    long_diag = "x" * 2000
    p = roles.critic_prompt("theorem t : 1 = 1", "rfl", long_diag)
    assert "theorem t : 1 = 1" in p
    assert len(p) < 2000  # 诊断被截断
    s = roles.strategist_prompt("theorem t : 1 = 1", "尝试 1: rfl 失败", "wrong_strategy")
    assert "wrong_strategy" in s and "theorem t" in s


def test_strategy_labels_is_subset():
    assert roles.STRATEGY_LABELS <= set(roles.CRITIC_LABELS)


@pytest.mark.parametrize(
    "text, label, conf",
    [
        ("induction: 85", "induction", 85),
        ("contradiction: 70 因为要反证", "contradiction", 70),
        ("direct: 120", "direct", 100),  # 上限截断
        ("Direct", "direct", 50),  # 无置信度 → 默认 50
        ("??", "other", 0),
        ("", "other", 0),
    ],
)
def test_parse_probe(text, label, conf):
    assert roles.parse_probe(text) == (label, conf)


def test_system_prompt_dispatch():
    from harness.models import system_prompt

    assert "诊断器" in system_prompt("critic")
    assert "策略顾问" in system_prompt("strategist")
    assert "策略顾问" in system_prompt("strategy_probe")
    assert "计划" in system_prompt("planner")
    # 未知角色退回 prover 的提示，避免静默丢角色
    assert "tactic 生成器" in system_prompt("nonsense")


def test_skeleton_system_prompt_allows_sorry():
    """回归：允许骨架时，系统提示**不能**再说「不要使用 sorry」。

    v0.6 第一版忘了改这句，结果 100 题里一个骨架都没出现。
    """
    from harness.models import system_prompt

    strict = system_prompt("prover")
    loose = system_prompt("prover", allow_skeleton=True)
    assert "不要使用 sorry" in strict
    assert "不要使用 sorry" not in loose
    assert "允许部分完成" in loose


@pytest.mark.parametrize(
    "text, outline_len, lemmas, has_pitfalls",
    [
        ("OUTLINE:\n1. 反证\n2. 化简\nLEMMAS: Nat.add_comm, Finset.sum_comm\nPITFALLS: 注意 0", 2, 2, True),
        ("OUTLINE:\n1. 归纳\nLEMMAS:\nPITFALLS:", 1, 0, False),
        ("没有按格式写的散文计划", 1, 0, False),  # 兜底：整段当 outline
        ("", 0, 0, False),
    ],
)
def test_parse_plan(text, outline_len, lemmas, has_pitfalls):
    p = roles.parse_plan(text)
    assert len(p["outline"]) == outline_len
    assert len(p["lemmas"]) == lemmas
    assert bool(p["pitfalls"]) is has_pitfalls


def test_parse_plan_drops_non_identifiers():
    p = roles.parse_plan("OUTLINE:\n1. a\nLEMMAS: Nat.add_comm, 这是一个句子, Foo.bar")
    assert p["lemmas"] == ["Nat.add_comm", "Foo.bar"]


def test_planner_prompt_includes_history():
    text = roles.planner_prompt("theorem t : 1 = 1", "尝试 1: rfl 失败", "旧计划")
    assert "尝试 1" in text and "旧计划" in text
