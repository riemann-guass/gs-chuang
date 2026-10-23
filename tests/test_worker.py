"""`harness/worker.py` 的离线单测（不启动 Lean）。

覆盖：命题字符串构造（`statement_type`）的各种边界、结果分类、
请求/响应的文件协议（用假的 worker 进程模拟）。
"""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest

from harness.worker import WorkerResult, binder_count, statement_type


@pytest.mark.parametrize(
    "header, want",
    [
        ("theorem foo (n : Nat) : n = n", 1),
        ("theorem foo (a b : ℂ) : a = b", 2),
        ("theorem foo (a b c : ℂ) : a = b", 3),
        ("theorem foo {n : Nat} : n = n", 1),
        ("theorem foo [Group G] (g : G) : g = g", 2),
        ("theorem foo : 1 = 1", 0),
        ("theorem foo (x : ℝ) (h : x = 1) : x = 1", 2),
        # 参数字组内部还有括号，不能被当成两组
        ("theorem foo (h : (a : Nat) = a) : a = a", 1),
    ],
)
def test_binder_count(header, want):
    assert binder_count(header) == want


@pytest.mark.parametrize(
    "header, want",
    [
        ("theorem foo : 1 = 1", "1 = 1"),
        ("theorem foo (n : Nat) : n + 0 = n", "∀ (n : Nat), n + 0 = n"),
        ("theorem foo (x : ℝ) (h : x = 1) : x = 1", "∀ (x : ℝ) (h : x = 1), x = 1"),
        ("lemma bar {n : Nat} : n = n", "∀ {n : Nat}, n = n"),
        ("theorem baz [Group G] (g : G) : g * 1 = g", "∀ [Group G] (g : G), g * 1 = g"),
        ("example : True", "True"),
    ],
)
def test_statement_type(header, want):
    assert statement_type(header) == want


def test_statement_type_rejects_non_theorem():
    with pytest.raises(ValueError):
        statement_type("def x : Nat := 0")


def test_statement_type_handles_nested_colon():
    # `(h : (a : Nat) = a)` 里的冒号不能被当成类型分隔符
    header = "theorem t (a : Nat) (h : (a : Nat) = a) : a = a"
    assert statement_type(header) == "∀ (a : Nat) (h : (a : Nat) = a), a = a"


def test_result_reason():
    assert WorkerResult(ok=True).reason == "ok"
    assert WorkerResult(ok=False, sorry=True).reason == "sorry"
    # 类别名与 harness.diagnostics.classify 对齐
    assert WorkerResult(ok=False, goals=2).reason == "unsolved_goals"
    assert WorkerResult(ok=False, error="cascade_exhausted").reason == "cascade_exhausted"


@pytest.mark.parametrize(
    "msg, want",
    [
        ("", "none"),
        ("cascade_exhausted\n⊢ 1 = 2", "cascade_exhausted"),
        ("unsolved goals", "unsolved_goals"),
        ("Type mismatch: ...", "type_mismatch"),
        ("unknown identifier 'foo'", "unknown_ident"),
        ("maximum recursion depth has been reached", "max_rec_depth"),
        ("maximum number of heartbeats (200000) has been reached", "heartbeat_limit"),
        ("linarith failed to find a contradiction", "tactic_error"),
        ("something weird", "other"),
    ],
)
def test_classify_worker_error(msg, want):
    from harness.worker import classify_worker_error

    assert classify_worker_error(msg) == want


def test_file_protocol_roundtrip():
    """用假进程验证「写 req_<seq> → 等 rsp_<seq>」的机制。

    文件名是纯 ASCII 且不带扩展名：Lean 侧对含多字节字符的文件名做 `endsWith`
    会触发 `String.Slice.pos!` panic，所以协议刻意避开了这类操作。
    """
    from harness.worker import LeanWorker

    work = Path(__file__).parent / "_tmp_worker_proto"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    class FakeProc:
        def poll(self):
            return None

    w = LeanWorker(work_dir=work, poll_s=0.01, request_timeout_s=5)
    w.proc = FakeProc()  # type: ignore[assignment]

    def responder():
        # 模拟 worker：看到 req 就写 rsp
        for _ in range(300):
            for req in work.glob("req_*"):
                out = work / req.name.replace("req_", "rsp_")
                if not out.exists():
                    payload = json.loads(req.read_text(encoding="utf-8"))
                    out.write_text(
                        json.dumps({"id": payload["id"], "ok": True, "goals": 0, "sorry": False}),
                        encoding="utf-8",
                    )
                break
            threading.Event().wait(0.01)

    th = threading.Thread(target=responder, daemon=True)
    th.start()
    result = w.check("(1 : Nat) = 1", "rfl")
    assert result.ok and result.goals == 0

    shutil.rmtree(work)
