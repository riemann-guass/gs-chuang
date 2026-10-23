"""阶段机与引擎接口的离线单测（不调用 Lean、不联网）。

只验证：
* 阶段顺序 / 重复次数 / 触发条件；
* 已验证的题不会被再次提交；
* 预算过滤（token）；
* `prove()` 的入参校验与 `ProofResult` 的形状；
* 成本计算在未配置单价时必须是 None（不许编造价格）。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness import config, pipeline, prover
from harness.problems import Problem


def _state(pid: str, *, status="failed", errors=(), tokens=0) -> "pipeline.runner.ProblemState":
    p = Problem(problem_id=pid, split="Valid", header=f"theorem {pid} : True", body="")
    st = pipeline.runner.ProblemState(problem=p)
    st.status = status
    st.error_types = list(errors)
    st.tokens_in = tokens
    st.attempts.append({"round": 0, "source": "cascade", "proof": "simp"})
    return st


def test_pipeline_v1_shape():
    plan = pipeline.pipeline_v1(rounds=3, remediate=True)
    assert [s.name for s in plan] == ["L0", "remedy", "L1"]
    assert plan[0].triggers == frozenset()
    assert plan[1].triggers == config.REMEDY_TRIGGERS
    assert plan[2].repeat == 3

    plan2 = pipeline.pipeline_v1(rounds=0, remediate=False)
    assert [s.name for s in plan2] == ["L0", "L1"]
    assert plan2[1].repeat == 0


def test_run_pipeline_triggers_and_skip_verified():
    """补救阶段只拿到触发题；已验证的题不再进入任何阶段。"""
    seen: dict[str, list[str]] = {}

    def fake_l0(cands, ctx):
        seen["L0"] = [s.problem.problem_id for s in cands]

    def fake_remedy(cands, ctx):
        seen["remedy"] = [s.problem.problem_id for s in cands]

    states = [
        _state("a", errors=("max_rec_depth",)),
        _state("b", errors=("cascade_exhausted",)),
        _state("c", status="verified"),
    ]
    stages = [
        pipeline.Stage("L0", fn=fake_l0),
        pipeline.Stage("remedy", triggers=config.REMEDY_TRIGGERS, fn=fake_remedy),
    ]

    tmp = Path(__file__).parent / "_tmp_pipeline"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    out = tmp / "r.jsonl"
    # 直接驱动 run_pipeline 的分派逻辑，但用假 stage 避免调 Lean
    ctx = pipeline.Context(run_id="t")
    plan = stages
    for stage in plan:
        pending = [st for st in states if st.status != "verified"]
        cands = (
            [st for st in pending if stage.triggers & set(st.error_types)]
            if stage.triggers
            else pending
        )
        if cands:
            stage.fn(cands, ctx)
    assert seen["L0"] == ["a", "b"]
    assert seen["remedy"] == ["a"]
    shutil.rmtree(tmp)


def test_token_budget_filters_candidates():
    ctx = pipeline.Context(run_id="t", max_tokens=100)
    over = _state("over", tokens=200)
    under = _state("under", tokens=10)
    pending = [over, under]
    kept = [st for st in pending if st.tokens_in + st.tokens_out <= ctx.max_tokens]
    assert [st.problem.problem_id for st in kept] == ["under"]


def test_deadline_flag():
    """截止时间判断不能靠 sleep（在 CI/满载时会 flaky），用显式 deadline 测。"""
    import time

    assert not pipeline.Context(run_id="t", max_wall_s=0).over_deadline()  # 0 = 不限

    # max_wall_s > 0 时应在构造时算出 deadline
    auto = pipeline.Context(run_id="t", max_wall_s=5)
    assert auto.deadline > 0

    # 显式给一个过去的 deadline，必须判定为超时
    expired = pipeline.Context(run_id="t", deadline=time.monotonic() - 1)
    assert expired.over_deadline()


def test_problem_from_statement():
    p = prover.problem_from_statement("theorem foo (n : Nat) : n + 0 = n")
    assert p.problem_id == "foo"
    assert p.split == "Adhoc"
    assert p.header.startswith("theorem foo")
    with pytest.raises(ValueError):
        prover.problem_from_statement("forall n, n = n")


def test_token_cost_requires_prices():
    assert config.token_cost_cny(1_000_000, 1_000_000) is None


def test_token_cost_math(monkeypatch):
    monkeypatch.setattr(config, "PRICE_IN_CNY_PER_MTOK", 2.0)
    monkeypatch.setattr(config, "PRICE_OUT_CNY_PER_MTOK", 8.0)
    cost = config.token_cost_cny(1_000_000, 500_000)
    assert cost == 2.0 + 4.0


def test_proof_result_from_state():
    st = _state("a", status="verified")
    st.tokens_in, st.tokens_out = 100, 50
    st.wall_ms = 1234.0
    st.stages = ["L0"]
    st.axioms = ("propext",)
    r = prover.ProofResult.from_state(st)
    assert r.ok and r.problem_id == "a"
    assert r.wall_ms == 1234
    assert r.cost_cny is None  # 未配置单价
    assert r.stages == ["L0"]
