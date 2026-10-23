"""模型层的离线单测：不联网、不读真实 .env。"""

from __future__ import annotations

from harness.models import DeepSeekClient, MockModel, build_model, extract_proof


def test_extract_proof_handles_fences():
    assert extract_proof("```lean4\nnorm_num\n```") == "norm_num"
    assert extract_proof("```lean\nsimp\n```") == "simp"
    assert extract_proof("```\nring\n```") == "ring"


def test_extract_proof_without_fence():
    assert extract_proof("  linarith  ") == "linarith"


def test_extract_proof_drops_comment_lines():
    text = "```lean4\n-- 先化简\nsimp\n```"
    assert extract_proof(text) == "simp"


def test_build_model_falls_back_to_mock():
    model, note = build_model({}, allow_network=True)
    assert isinstance(model, MockModel)
    assert note == "missing-key-fallback-mock"


def test_build_model_no_network_requested():
    model, note = build_model(
        {"DEEPSEEK_BASE_URL": "https://x/v1", "DEEPSEEK_API_KEY": "k"}, allow_network=False
    )
    assert isinstance(model, MockModel)
    assert note == "no-network-requested"


def test_build_model_creates_client_without_proxy():
    model, note = build_model(
        {"DEEPSEEK_BASE_URL": "https://x/v1", "DEEPSEEK_API_KEY": "k", "DEEPSEEK_MODEL": "m1"},
        allow_network=True,
    )
    assert isinstance(model, DeepSeekClient)
    assert model.name == "m1"
    assert model.proxies is None
    assert note == "deepseek"


def test_build_model_passes_proxy():
    model, _ = build_model(
        {
            "DEEPSEEK_BASE_URL": "https://x/v1",
            "DEEPSEEK_API_KEY": "k",
            "DEEPSEEK_PROXY": "http://127.0.0.1:7897",
        },
        allow_network=True,
    )
    assert isinstance(model, DeepSeekClient)
    assert model.proxies == {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}


def test_mock_is_deterministic_and_cycles():
    m = MockModel()
    from harness.models import ProposeRequest
    from harness.problems import Problem

    p = Problem(problem_id="x", split="Valid", header="theorem x : True", body="sorry")
    first = m.propose(ProposeRequest(problem=p, attempt_index=0)).proof
    again = m.propose(ProposeRequest(problem=p, attempt_index=0)).proof
    assert first == again
    later = m.propose(ProposeRequest(problem=p, attempt_index=3)).proof
    assert later != first


def test_connection_error_is_classified():
    """连不上的端口要变成 ModelError，而不是裸 requests 异常。"""
    import pytest

    from harness.models import ModelError, ProposeRequest
    from harness.problems import Problem

    client = DeepSeekClient(
        base_url="http://127.0.0.1:1/v1",  # 1 号端口不会有人监听
        api_key="k",
        model="m",
        timeout_s=2,
    )
    p = Problem(problem_id="x", split="Valid", header="theorem x : True", body="sorry")
    with pytest.raises(ModelError) as ei:
        client.propose(ProposeRequest(problem=p, attempt_index=0))
    assert ei.value.kind in {"connection", "timeout", "unknown"}


def test_extract_proof_unclosed_fence_drops_lang_tag():
    """回归：围栏没闭合时不能把 `lean4` 留给 Lean 当 tactic。

    2026-10-21 的真实失败输出：
        ```lean4
        have h4 : ... := by ...
        （被 max_tokens 截断，没有闭合围栏）
    早期版本去掉 ``` 之后把 `lean4` 当成了第一行，Lean 报 `unknown tactic`。
    """
    raw = "```lean4\nhave h4 : a = a := rfl\nrw [h4]"
    out = extract_proof(raw)
    assert not out.startswith("lean4")
    assert out.splitlines()[0].startswith("have h4")


def test_extract_proof_bare_lang_tag_line():
    assert extract_proof("lean4\nsimp") == "simp"
    assert extract_proof("```\nlean\nring\n```") == "ring"


def test_extract_proof_keeps_multiline():
    raw = "```lean4\nhave h : 1 = 1 := rfl\nsimp [h]\n```"
    out = extract_proof(raw)
    assert out == "have h : 1 = 1 := rfl\nsimp [h]"


def test_build_model_reads_max_tokens():
    model, _ = build_model(
        {
            "DEEPSEEK_BASE_URL": "https://x/v1",
            "DEEPSEEK_API_KEY": "k",
            "DEEPSEEK_MAX_TOKENS": "256",
        },
        allow_network=True,
    )
    assert model.max_tokens == 256
