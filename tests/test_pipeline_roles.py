"""Critic / Strategist 两个阶段的行为测试（离线，不调 Lean）。

关注四件事：
1. Critic 只处理「有失败尝试」的题，且把标签写回黑板；
2. Strategist 的门控（策略类标签 or 连续失败 ≥ 3）；
3. **写者唯一**：Strategist 的产物只进 `st.strategy`，绝不变成可编译的 proof；
4. 模型报错时不影响其它题。
"""

from __future__ import annotations

from harness import pipeline
from harness.models import ModelError, ModelResponse
from harness.problems import Problem


class FakeModel:
    name = "fake"

    def __init__(self, text: str = "wrong_strategy: 方向错", *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls: list[str] = []

    def propose(self, req):  # noqa: ANN001
        self.calls.append(req.role)
        if self.fail:
            raise ModelError("connection", "boom")
        return ModelResponse(proof=self.text, text=self.text, tokens_in=10, tokens_out=5)


def _state(pid: str = "p", *, status: str = "failed", attempts: int = 1) -> pipeline.runner.ProblemState:
    p = Problem(problem_id=pid, split="Valid", header=f"theorem {pid} : True", body="")
    st = pipeline.runner.ProblemState(problem=p)
    st.status = status
    for i in range(attempts):
        st.attempts.append(
            {
                "round": i,
                "source": "cascade",
                "proof": "simp",
                "status": "failed",
                "error_kind": "cascade_exhausted",
                "diagnostics": "⊢ True",
            }
        )
    return st


def test_stage_critic_writes_label_and_tokens():
    st = _state()
    model = FakeModel("wrong_strategy: 应该反证")
    ctx = pipeline.Context(run_id="t")
    pipeline.stage_critic([st], ctx, model=model)
    assert st.critic_label == "wrong_strategy"
    assert "反证" in st.critic_note
    assert st.tokens_in == 10 and st.tokens_out == 5
    assert any(s.startswith("critic#") for s in st.stages)
    assert model.calls == ["critic"]


def test_stage_critic_survives_api_error():
    st = _state()
    ctx = pipeline.Context(run_id="t")
    pipeline.stage_critic([st], ctx, model=FakeModel(fail=True))
    assert st.critic_label == "other"
    assert "api_error" in st.critic_note


def test_needs_critic_skips_verified_and_empty():
    assert pipeline.needs_critic(_state(status="failed", attempts=1))
    assert not pipeline.needs_critic(_state(status="verified", attempts=1))
    assert not pipeline.needs_critic(_state(status="failed", attempts=0))


def test_needs_strategist_gating():
    by_label = _state()
    by_label.critic_label = "wrong_strategy"
    assert pipeline.needs_strategist(by_label)

    by_rounds = _state()
    by_rounds.critic_label = "syntax"
    by_rounds.failed_rounds = 3
    assert pipeline.needs_strategist(by_rounds)

    neither = _state()
    neither.critic_label = "syntax"
    neither.failed_rounds = 1
    assert not pipeline.needs_strategist(neither)

    done = _state(status="verified")
    done.critic_label = "wrong_strategy"
    assert not pipeline.needs_strategist(done)


def test_stage_strategist_never_writes_proof():
    """写者唯一：策略只能进 `strategy` 字段，不能变成 proof。"""
    st = _state()
    st.critic_label = "needs_induction"
    before_proof = st.proof
    model = FakeModel("STRATEGY: 对 n 归纳\nSKETCH: step 用 simp [ih]")
    ctx = pipeline.Context(run_id="t")
    pipeline.stage_strategist([st], ctx, model=model)
    assert st.proof == before_proof  # 没被写
    assert "归纳" in st.strategy
    assert "simp [ih]" in st.strategy
    # 策略也没有被塞进 attempts（attempts 只记录真正编译过的证明）
    assert all(a["source"] != "fake" for a in st.attempts)
    assert model.calls == ["strategist"]


def test_critic_note_reaches_prover_prompt():
    """回归：Critic 的**建议正文**必须进 Prover 的 prompt。

    v0.5 只把 `critic_label`（一个词）传下去，Prover 只看到 `unsolved`，
    等于没传——A/B 因此测的是"多一个词"，而不是"多一条建议"。
    """
    from harness.models import ProposeRequest, render_prompt

    p = Problem(problem_id="p", split="Valid", header="theorem p (n : Nat) : n = n", body="")
    req = ProposeRequest(
        problem=p,
        attempt_index=1,
        critic_label="unsolved",
        critic_note="需补 x²+y² 展开关系，再用 nlinarith",
    )
    text = render_prompt(req)
    assert "需补 x²+y² 展开关系" in text
    assert "诊断建议" in text


def test_critic_prompt_includes_full_history():
    """Critic 要看到多次失败，而不是只看最后一次。"""
    from harness import roles

    text = roles.critic_prompt(
        "theorem p : 1 = 1",
        "尝试 1（cascade, failed）：simp\n尝试 2（flash, failed）：norm_num",
        "unsolved",
    )
    assert "尝试 1" in text and "尝试 2" in text


def test_failed_rounds_bump_only_for_unverified():
    a, b = _state("a"), _state("b", status="verified")
    pipeline._bump_failed_rounds([a, b])
    assert a.failed_rounds == 1
    assert b.failed_rounds == 0


# ------------------------------------------------------------ 计划与骨架
def test_needs_plan_schedule():
    st = _state()
    assert pipeline.needs_plan(st)  # 没有计划 → 生成 v1
    st.plan = {"outline": ["x"]}
    st.failed_rounds = 1
    assert not pipeline.needs_plan(st)  # 非检查点
    st.failed_rounds = 2
    assert pipeline.needs_plan(st)  # 2^n 检查点
    st.failed_rounds = 4
    assert pipeline.needs_plan(st)
    st.status = "verified"
    assert not pipeline.needs_plan(st)


def test_stage_plan_writes_version_and_history():
    st = _state()
    model = FakeModel("OUTLINE:\n1. 反证\nLEMMAS: Nat.add_comm\nPITFALLS: 注意 0")
    ctx = pipeline.Context(run_id="t")
    pipeline.stage_plan([st], ctx, model=model)
    assert st.plan_version == 1
    assert st.plan["lemmas"] == ["Nat.add_comm"]
    assert st.plan_history == [{"version": 1, "at_round": 0}]
    assert model.calls == ["planner"]
    assert any(s.startswith("plan#v") for s in st.stages)

    # 第二次（检查点）应升到 v2 并记录
    st.failed_rounds = 2
    pipeline.stage_plan([st], ctx, model=model)
    assert st.plan_version == 2
    assert st.plan_history[-1] == {"version": 2, "at_round": 2}


def test_stage_plan_survives_api_error():
    st = _state()
    ctx = pipeline.Context(run_id="t")
    pipeline.stage_plan([st], ctx, model=FakeModel(fail=True))
    assert st.plan_version == 0 and st.plan == {}


def _with_worker(st, *, compiles, sorries):
    st.attempts[-1]["worker"] = {"compiles": compiles, "sorries": sorries, "ok": False, "goals": 0}
    return st


def test_record_progress_accepts_single_sorry_skeleton():
    st = _with_worker(_state(), compiles=True, sorries=1)
    pipeline._record_progress(st, 3)
    assert st.best_skeleton is not None
    assert st.best_skeleton["sorries"] == 1
    assert st.best_skeleton["at_round"] == 3
    assert st.status != "verified"  # 骨架永远不算通过


def test_record_progress_rejects_too_many_sorries_or_no_compile():
    st = _with_worker(_state(), compiles=True, sorries=3)
    pipeline._record_progress(st, 1)
    assert st.best_skeleton is None

    st2 = _with_worker(_state(), compiles=False, sorries=1)
    pipeline._record_progress(st2, 1)
    assert st2.best_skeleton is None


def test_record_progress_keeps_fewest_sorries():
    st = _with_worker(_state(), compiles=True, sorries=1)
    pipeline._record_progress(st, 1)
    st.best_skeleton = {"proof": "old", "sorries": 1, "at_round": 1}
    st.attempts.append({"round": 2, "source": "m", "proof": "new", "status": "failed"})
    st.attempts[-1]["worker"] = {"compiles": True, "sorries": 1, "ok": False, "goals": 0}
    pipeline._record_progress(st, 2)
    assert st.best_skeleton["proof"] == "old"  # 没有更少，不覆盖
