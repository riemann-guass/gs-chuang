"""`harness/server.py` 的离线单测：不起 Lean、不起真模型。

用假的 service 验证路由、状态码、请求体校验。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from harness import server
from harness.worker import WorkerResult


def test_as_problem_wraps_bare_proposition():
    p = server.as_problem("(1 : Nat) + 1 = 2")
    assert p.header == "example : (1 : Nat) + 1 = 2"
    p2 = server.as_problem("theorem foo (n : Nat) : n = n")
    assert p2.header.startswith("theorem foo")
    with pytest.raises(ValueError):
        server.as_problem("   ")


def test_check_payload_shape():
    payload = server._check_payload(WorkerResult(ok=False, goals=2, error="unsolved"))
    assert payload["ok"] is False
    assert payload["goals"] == 2
    assert payload["reason"] == "unsolved_goals"


class _FakeService:
    """只实现 handler 需要的接口。"""

    def __init__(self) -> None:
        self.stats = server.ServerStats()

    def health(self):
        return {"ok": True, "warmup_s": 1.0}

    def check(self, statement, proof):
        return {"ok": statement == "good" and proof == "rfl", "reason": "x"}

    def prove(self, statement):
        return {"ok": True, "proof": "rfl", "stage": "L0"}


@pytest.fixture()
def live_server():
    svc = _FakeService()
    httpd = HTTPServer(("127.0.0.1", 0), server.make_handler(svc))  # type: ignore[arg-type]
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


def _post(base: str, path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_health(live_server):
    with urllib.request.urlopen(live_server + "/health", timeout=10) as r:
        body = json.loads(r.read().decode())
    assert body["ok"] is True


def test_check_ok_and_missing_fields(live_server):
    code, body = _post(live_server, "/check", {"statement": "good", "proof": "rfl"})
    assert code == 200 and body["ok"] is True

    code, body = _post(live_server, "/check", {"statement": "good"})
    assert code == 400 and body["ok"] is False


def test_prove_and_unknown_route(live_server):
    code, body = _post(live_server, "/prove", {"statement": "anything"})
    assert code == 200 and body["ok"] is True and body["stage"] == "L0"

    code, body = _post(live_server, "/nope", {})
    assert code == 404
