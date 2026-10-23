"""诊断 → 对策 映射的单测（离线）。"""

from __future__ import annotations

from harness import hints
from harness.diagnostics import Diagnostic


def test_hints_for_known_kind():
    hs = hints.hints_for(["max_rec_depth"])
    assert len(hs) == 2
    assert all("maxRecDepth" in h or "exponentiation" in h for h in hs)


def test_hints_unknown_kind_falls_back_to_generic():
    hs = hints.hints_for(["something_new"])
    assert hs == [hints._GENERIC]


def test_hints_dedup_and_order():
    hs = hints.hints_for(["cascade_exhausted", "cascade_exhausted", "max_rec_depth"])
    assert hs[0].startswith("No single cheap tactic")
    assert len(hs) == 4  # 2 from cascade + 2 from max_rec_depth


def test_render_hints_is_bulleted():
    text = hints.render_hints(["type_mismatch"])
    assert text.startswith("- ")
    assert text.count("\n- ") == 0  # 只有一条


def test_kinds_from_diagnostics():
    ds = [
        Diagnostic(severity="error", message="maximum recursion depth has been reached", file="x", line=1, col=1),
        Diagnostic(severity="error", message="maximum recursion depth has been reached", file="x", line=2, col=1),
        Diagnostic(severity="error", message="unknown identifier 'foo'", file="x", line=3, col=1),
        Diagnostic(severity="warning", message="declaration uses `sorry`", file="x", line=4, col=1),
    ]
    kinds = hints.kinds_from_diagnostics(ds)
    assert kinds == ["max_rec_depth", "unknown_identifier"]


def test_every_classifier_kind_has_a_countermeasure_or_is_intentional():
    """所有 classify() 可能返回的类型，应当要么有对策、要么明确是「无建议」。"""
    from harness.diagnostics import classify

    known = set(hints.COUNTERMEASURES)
    intentional = {"none", "batch_timeout", "batch_truncated", "sorry"}
    possible = {
        "none",
        "arithmetic_unclosed",
        "cascade_exhausted",
        "max_rec_depth",
        "exponent_threshold",
        "unsolved_goals",
        "unknown_identifier",
        "type_mismatch",
        "tactic_error",
        "syntax_error",
        "other",
    }
    assert possible <= known | intentional, f"缺对策: {possible - known - intentional}"
    # 抽查两个真实分类
    assert classify([Diagnostic("error", "maximum recursion depth has been reached", "x", 1, 1)]) == "max_rec_depth"
