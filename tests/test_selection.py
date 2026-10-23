"""选题与统计的单测（离线）。

覆盖 WP1 引入的两件事：
1. `select_problems` 的 `split` 过滤；
2. `family_of` 的家族归并规则（`mathd_algebra_10` -> `mathd_algebra`）。
"""

from __future__ import annotations

from harness import metrics
from harness.cli import STRATIFIED_10, select_problems
from harness.problems import Problem, family_of


def _p(pid: str, split: str = "Valid") -> Problem:
    return Problem(problem_id=pid, split=split, header=f"theorem {pid} : True", body="sorry")


def test_family_of():
    assert family_of("mathd_algebra_10") == "mathd_algebra"
    assert family_of("mathd_numbertheory_961") == "mathd_numbertheory"
    assert family_of("amc12a_2002_p1") == "amc12a"
    assert family_of("amc12b_2021_p1") == "amc12b"
    assert family_of("induction_sum_odd") == "induction"
    assert family_of("imo_1961_p1") == "imo"
    assert family_of("aime_1983_p1") == "aime"
    # 未知前缀退化为第一段，不能抛异常
    assert family_of("weird_name") == "weird"


def test_select_filters_by_split():
    problems = [_p("mathd_algebra_1", "Valid"), _p("mathd_algebra_2", "Valid"), _p("mathd_algebra_3", "Test")]
    picked = select_problems(problems, "all", split="Valid")
    assert [p.problem_id for p in picked] == ["mathd_algebra_1", "mathd_algebra_2"]
    picked_test = select_problems(problems, "all", split="Test")
    assert [p.problem_id for p in picked_test] == ["mathd_algebra_3"]


def test_select_stratified_respects_split_and_order():
    problems = [_p(f"mathd_algebra_{i}") for i in (3, 1, 2)]
    problems += [_p("induction_b"), _p("induction_a")]
    problems.append(_p("imo_1961_p1"))
    picked = select_problems(problems, "stratified10", split="Valid")
    ids = [p.problem_id for p in picked]
    # mathd_algebra_ 要 4 题但只有 3 题；按 id 排序保证可复现
    assert ids == [
        "mathd_algebra_1",
        "mathd_algebra_2",
        "mathd_algebra_3",
        "induction_a",
        "induction_b",
        "imo_1961_p1",
    ]


def test_summary_by_family():
    records = [
        {"problem_id": "mathd_algebra_1", "status": "verified", "attempts": [], "time_ms": 0},
        {"problem_id": "mathd_algebra_2", "status": "failed", "attempts": [], "time_ms": 0},
        {"problem_id": "induction_a", "status": "verified", "attempts": [], "time_ms": 0},
    ]
    s = metrics.summarize(records)
    fam = s.by_family()
    assert fam["mathd_algebra"] == {"total": 2, "verified": 1, "pass@1": 0.5}
    assert fam["induction"] == {"total": 1, "verified": 1, "pass@1": 1.0}
    assert abs(s.pass_at_1 - 2 / 3) < 1e-9
    assert s.as_dict()["pass@1"] == 0.6667  # 只有 as_dict 才四舍五入


def test_record_carries_family_and_ladder_version():
    from harness import config, runner

    st = runner.ProblemState(problem=_p("mathd_algebra_7"))
    rec = st.to_record(run_id="r", model_name="none")
    assert rec["family"] == "mathd_algebra"
    assert rec["ladder_version"] == config.LADDER_VERSION
    assert rec["max_heartbeats"] == config.MAX_HEARTBEATS
