"""用真实捕获的编译器输出做解析/审计单测（离线、毫秒级）。

输出文本来自 2026-10-19 的探测批次
（`lean/Bench/_work/batch_probe2.lean`，4 道题：1 个正常、1 个失败、
1 个 sorry、1 个正常），原样粘贴，确保解析器对着真格式而不是想象。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from harness import diagnostics, verify
from harness.leanenv import BatchItem, Span, render_batch

PROBE_OUTPUT = """\
'BatchProbe2.t1_ok' depends on axioms: [propext, Classical.choice, Quot.sound]
D:\\bianma\\code\\大创2\\lean\\Bench\\_work\\batch_probe2.lean:15:2: error: linarith failed to find a contradiction
x : ℝ
h : x ^ 2 - 5 * x - 4 ≤ 10
⊢ False
failed
'BatchProbe2.t2_fail' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
D:\\bianma\\code\\大创2\\lean\\Bench\\_work\\batch_probe2.lean:19:8: warning: declaration uses `sorry`
'BatchProbe2.t3_sorry' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
'BatchProbe2.t4_after' does not depend on any axioms
"""

SPANS = {
    "t1_ok": Span(6, 11, 10),
    "t2_fail": Span(12, 18, 17),
    "t3_sorry": Span(19, 25, 24),
    "t4_after": Span(26, 31, 30),
}
QUALIFIED = {
    "t1_ok": "BatchProbe2.t1_ok",
    "t2_fail": "BatchProbe2.t2_fail",
    "t3_sorry": "BatchProbe2.t3_sorry",
    "t4_after": "BatchProbe2.t4_after",
}


def test_parse_separates_axioms_from_diagnostics():
    parsed = diagnostics.parse(PROBE_OUTPUT)
    assert len(parsed.diagnostics) == 2
    err = parsed.errors()[0]
    assert err.line == 15 and err.severity == "error"
    # goal state 必须挂在这条错误上，而不是丢失
    assert "x ^ 2 - 5 * x - 4 ≤ 10" in err.detail
    assert "⊢ False" in err.detail
    warn = parsed.warnings()[0]
    assert warn.line == 19 and "declaration uses" in warn.message and "sorry" in warn.message


def test_axiom_reports():
    parsed = diagnostics.parse(PROBE_OUTPUT)
    assert set(parsed.axioms) == set(QUALIFIED.values())
    assert parsed.axioms["BatchProbe2.t1_ok"].axioms == ("propext", "Classical.choice", "Quot.sound")
    assert parsed.axioms["BatchProbe2.t2_fail"].uses_sorry
    assert parsed.axioms["BatchProbe2.t4_after"].axioms == ()
    assert not parsed.axioms["BatchProbe2.t4_after"].uses_sorry


def test_locate_spans():
    parsed = diagnostics.parse(PROBE_OUTPUT)
    located = diagnostics.locate_spans(parsed.diagnostics, SPANS)
    assert [d.line for d in located["t2_fail"]] == [15]
    assert [d.line for d in located["t3_sorry"]] == [19]
    assert located["t1_ok"] == []
    assert located["t4_after"] == []


def test_audit_four_outcomes():
    parsed = diagnostics.parse(PROBE_OUTPUT)
    located = diagnostics.locate_spans(parsed.diagnostics, SPANS)

    ok = verify.audit_problem(
        problem_id="t1_ok",
        proof="norm_num",
        qualified_name=QUALIFIED["t1_ok"],
        span_diagnostics=located["t1_ok"],
        axioms=parsed.axioms,
    )
    assert ok.ok, ok.reasons
    assert ok.axioms == ("propext", "Classical.choice", "Quot.sound")

    failed = verify.audit_problem(
        problem_id="t2_fail",
        proof="linarith",
        qualified_name=QUALIFIED["t2_fail"],
        span_diagnostics=located["t2_fail"],
        axioms=parsed.axioms,
    )
    assert not failed.ok
    assert any(r.startswith("compile_error") for r in failed.reasons)
    assert "sorry_ax" in failed.reasons

    sorry = verify.audit_problem(
        problem_id="t3_sorry",
        proof="sorry",
        qualified_name=QUALIFIED["t3_sorry"],
        span_diagnostics=located["t3_sorry"],
        axioms=parsed.axioms,
    )
    assert not sorry.ok
    assert "forbidden_token:sorry" in sorry.reasons
    assert "sorry_ax" in sorry.reasons

    after = verify.audit_problem(
        problem_id="t4_after",
        proof="rfl",
        qualified_name=QUALIFIED["t4_after"],
        span_diagnostics=located["t4_after"],
        axioms=parsed.axioms,
    )
    assert after.ok, after.reasons


def test_render_batch_line_numbers():
    tmp = Path(__file__).parent / "_tmp_render"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    items = [
        BatchItem("p1", "theorem p1 (n : Nat) : n + 0 = n", "rfl"),
        BatchItem("p2", "theorem p2 (n : Nat) : n = n", "simp"),
    ]
    batch = render_batch(items, tmp / "b.lean")
    lines = batch.text.splitlines()
    for pid, span in batch.spans.items():
        assert "theorem" in lines[span.first_line - 1]
        assert lines[span.axioms_line - 1].startswith("#print axioms")
    assert batch.qualified_names["p1"] == "M0000.p1"
    assert batch.qualified_names["p2"] == "M0001.p2"
    shutil.rmtree(tmp)


def test_multiline_header_gets_by_on_last_line():
    """回归：多行声明时 `:= by` 必须接在最后一行。

    早期版本接在第一行，产生 `... : := by`，Lean 报
    `unexpected token ':='; expected term` —— M1 首轮有 4 道题因此被误判为语法错误。
    """
    tmp = Path(__file__).parent / "_tmp_multiline"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    header = "theorem p3 (x : ℝ) (h : x > 0) :\n    x ≠ 0"
    batch = render_batch([BatchItem("p3", header, "linarith")], tmp / "c.lean")
    lines = batch.text.splitlines()
    span = batch.spans["p3"]
    head = lines[span.first_line - 1]
    tail = lines[span.first_line]
    assert head.startswith("theorem p3")
    assert not head.rstrip().endswith(":="), head
    assert tail.strip().endswith(":= by"), tail
    shutil.rmtree(tmp)


def test_build_preamble_extra_options():
    """回归：`--extra-opt maxRecDepth=10000` 要渲染成 `set_option maxRecDepth 10000`。

    Lean 的语法是空格分隔，写成 `set_option maxRecDepth=10000` 会解析失败。
    """
    from harness.leanenv import build_preamble

    text = build_preamble(["maxRecDepth=10000", "exponentiation.threshold=10000"])
    assert "set_option maxRecDepth 10000" in text
    assert "set_option exponentiation.threshold 10000" in text
    assert "maxRecDepth=10000" not in text
    # 默认前缀不含额外 option
    assert "maxRecDepth" not in build_preamble()


def test_classify_cascade_sentinel():
    d = diagnostics.Diagnostic(severity="error", message="cascade_exhausted", file="x", line=1, col=1)
    assert diagnostics.classify([d]) == "cascade_exhausted"
    arith = diagnostics.Diagnostic(
        severity="error", message="linarith failed to find a contradiction", file="x", line=1, col=1
    )
    assert diagnostics.classify([arith]) == "arithmetic_unclosed"
    assert diagnostics.classify([]) == "none"


def test_cascade_uses_tactic_level_sentinel():
    """回归：哨兵必须是 `fail`（tactic），不能用 `throwError`（term 命令）。

    实测 `throwError` 会让 `first` 整条表达式解析失败（unexpected token），
    M1 因此从 4/10 掉到 0/10。
    """
    from harness.cascade import cascade_proof

    proof = cascade_proof()
    assert proof.startswith("first |")
    assert 'fail "cascade_exhausted"' in proof
    assert "throwError" not in proof


#: 真实捕获（2026-10-20，`runs/m1-valid244b-...-c00.lean.log`）：
#: 定理名太长时 `#print axioms` 被 Lean 按 80 列折行。
WRAPPED_AXIOM = """\
'M0019.algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta' depends on axioms: [propext,
 Classical.choice,
 Quot.sound]]
D:\\bianma\\code\\大创2\\lean\\Bench\\_work\\m1-valid244b.lean:158:218: error: cascade_exhausted
⊢ x = 26
'M0031.induction_sum_odd' does not depend on any axioms
"""


def test_parse_wrapped_axiom_line():
    """回归：折行的公理输出必须能拼回来。

    这个 bug 让 `algebra_3rootspoly_...` 拿不到公理报告，被误判成
    `batch_truncated`（看起来像 Lean 崩了），实际只是解析器要求整条在一行。
    """
    parsed = diagnostics.parse(WRAPPED_AXIOM)
    name = "M0019.algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta"
    assert name in parsed.axioms
    assert parsed.axioms[name].axioms == ("propext", "Classical.choice", "Quot.sound")
    assert not parsed.axioms[name].uses_sorry
    assert parsed.axioms["M0031.induction_sum_odd"].axioms == ()
    # 折行之后的那条错误仍然要能被解析，且不能吞掉后续公理
    assert [d.line for d in parsed.errors()] == [158]


def test_classify_recursion_depth():
    d = diagnostics.Diagnostic(
        severity="error",
        message="maximum recursion depth has been reached\nuse `set_option maxRecDepth <num>`",
        file="x",
        line=1,
        col=1,
    )
    assert diagnostics.classify([d]) == "max_rec_depth"


def test_lean_argv_disables_max_errors():
    """回归：`-DmaxErrors=0` 必须在命令行上。

    Lean 默认 100 个错误就退出；批量文件里这会静默吞掉后面所有题。
    实测 `set_option maxErrors 0` 写在文件里**无效**，只能用 `-D`。
    """
    from pathlib import Path as _P

    from harness.leanenv import lean_argv

    argv = lean_argv(_P("x.lean"))
    assert argv[:3] == ["lake", "env", "lean"]
    assert "-DmaxErrors=0" in argv
    assert argv[-1] == "x.lean"


def test_forbidden_tokens_are_word_bounded():
    assert verify.forbidden_tokens("by simp") == []
    assert verify.forbidden_tokens("by sorry") == ["sorry"]
    # native_decide 是禁用项，但 native_decides 不是
    assert verify.forbidden_tokens("by native_decide") == ["native_decide"]
