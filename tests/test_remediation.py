"""确定性补救（第二遍）的离线单测。

不调用 Lean：用假的编译结果驱动 `run_cascade` 的分支逻辑，
只验证「哪些题会进入补救轮」和「补救成功后状态怎么变」。
"""

from __future__ import annotations

import pytest

from harness import config, runner
from harness.leanenv import BatchItem, CompileResult, render_batch
from harness.problems import Problem


def _state(pid: str) -> runner.ProblemState:
    p = Problem(problem_id=pid, split="Valid", header=f"theorem {pid} : True", body="sorry")
    st = runner.ProblemState(problem=p)
    st.attempts.append({"round": 0, "source": "cascade", "proof": "simp"})
    return st


def test_remedy_trigger_set():
    assert "max_rec_depth" in config.REMEDY_TRIGGERS
    assert "exponent_threshold" in config.REMEDY_TRIGGERS
    assert "cascade_exhausted" not in config.REMEDY_TRIGGERS
    # 心跳必须有界，否则 simp 会跑飞（见 m3-deterministic-remediation.md）
    assert any(o.startswith("maxHeartbeats=") for o in config.REMEDY_OPTIONS)


def test_only_triggered_states_are_candidates():
    hit = _state("a")
    hit.status = "failed"
    hit.error_types = ["max_rec_depth"]
    miss = _state("b")
    miss.status = "failed"
    miss.error_types = ["cascade_exhausted"]
    done = _state("c")
    done.status = "verified"

    cands = [
        st
        for st in [hit, miss, done]
        if st.status != "verified" and (config.REMEDY_TRIGGERS & set(st.error_types))
    ]
    assert [st.problem.problem_id for st in cands] == ["a"]


def test_verified_clears_error_types():
    """补救成功后，旧失败类型不应留在汇总字段里。"""
    from pathlib import Path
    import shutil

    work = Path(__file__).parent / "_tmp_remedy"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    st = _state("a")
    st.status = "failed"
    st.error_types = ["max_rec_depth"]
    st.attempts.append({"round": 1, "source": "cascade-remedy", "proof": "simp"})

    batch = render_batch([BatchItem("a", st.problem.header, "simp")], work / "b.lean")
    qualified = batch.qualified_names["a"]
    result = CompileResult(
        returncode=0,
        output=f"'{qualified}' depends on axioms: [propext, Classical.choice, Quot.sound]\n",
        duration_ms=1000,
        path=batch.path,
    )
    runner._apply_audits([st], batch=batch, result=result, source="cascade-remedy")
    assert st.status == "verified"
    assert st.error_types == []
    assert st.attempts[-1]["status"] == "verified"
    shutil.rmtree(work)
