"""runner 的离线单测（不调用 Lean、不联网）。

关注的回归点：修复轮只把**未解决**的题提交编译时，`_apply_audits` 不能去查
不在本批次里的题 —— 早期版本在这里 KeyError，M2 的 mock 回路直接崩。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from harness import runner
from harness.leanenv import BatchItem, CompileResult, render_batch
from harness.problems import Problem


def _state(pid: str, split: str = "Valid") -> runner.ProblemState:
    p = Problem(problem_id=pid, split=split, header=f"theorem {pid} : True", body="sorry")
    st = runner.ProblemState(problem=p)
    st.attempts.append({"round": 0, "source": "cascade", "proof": "trivial"})
    return st


def _batch(problems: list[Problem], tmp: Path):
    items = [BatchItem(p.problem_id, p.header, "trivial") for p in problems]
    return render_batch(items, tmp / "b.lean")


def test_apply_audits_ignores_states_outside_batch():
    tmp = Path(__file__).parent / "_tmp_runner"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    st_a = _state("a")
    st_b = _state("b")
    # 批次里只有 a
    batch = _batch([st_a.problem], tmp)
    qualified = batch.qualified_names["a"]
    result = CompileResult(
        returncode=0,
        output=f"'{qualified}' depends on axioms: [propext, Classical.choice, Quot.sound]\n",
        duration_ms=1000,
        path=batch.path,
    )

    runner._apply_audits([st_a, st_b], batch=batch, result=result, source="cascade")

    assert st_a.status == "verified"
    # b 不在批次里，必须原样不动，且不能抛 KeyError
    assert st_b.status == "pending"
    assert st_b.time_ms == 0
    shutil.rmtree(tmp)


def test_apply_audits_marks_sorry_ax_as_failed():
    tmp = Path(__file__).parent / "_tmp_runner2"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    st = _state("a")
    batch = _batch([st.problem], tmp)
    qualified = batch.qualified_names["a"]
    result = CompileResult(
        returncode=1,
        output=f"'{qualified}' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]\n",
        duration_ms=1000,
        path=batch.path,
    )

    runner._apply_audits([st], batch=batch, result=result, source="cascade")
    assert st.status == "failed"
    assert "sorry_ax" in st.attempts[-1].get("error_kind", "") or st.attempts[-1]["status"] == "failed"
    shutil.rmtree(tmp)


def test_batch_timeout_is_error_not_failed():
    """回归：整块编译超时（returncode=-1）的题没有结论，不能算证明失败。"""
    tmp = Path(__file__).parent / "_tmp_runner4"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    st = _state("a")
    batch = _batch([st.problem], tmp)
    result = CompileResult(
        returncode=-1, output="[harness] 编译超时（900 s），已中止\n", duration_ms=900000, path=batch.path
    )

    runner._apply_audits([st], batch=batch, result=result, source="deepseek-flash")
    assert st.status == "error"
    assert "batch_timeout" in st.error_types
    shutil.rmtree(tmp)


def test_batch_truncated_is_error_not_failed():
    """回归：既无诊断也无公理报告的题，是「没跑到」，不是「证明失败」。

    2026-10-20 的 244 题单批次运行里，后 133 题就是这样被误记成 failed 的，
    差点得出「L0 只有 9/244」的错误结论（ADR-0004）。
    """
    tmp = Path(__file__).parent / "_tmp_runner3"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    st = _state("a")
    batch = _batch([st.problem], tmp)
    result = CompileResult(returncode=1, output="", duration_ms=1000, path=batch.path)

    runner._apply_audits([st], batch=batch, result=result, source="cascade")
    assert st.status == "error"
    assert "batch_truncated" in st.error_types
    shutil.rmtree(tmp)


def test_guard_split_blocks_test_set():
    p = Problem(problem_id="t", split="Test", header="theorem t : True", body="sorry")
    try:
        runner._guard_split([p], allow_test=False)
    except SystemExit:
        pass
    else:
        raise AssertionError("Test 集未被拦截")
    runner._guard_split([p], allow_test=True)  # 显式允许时放行
