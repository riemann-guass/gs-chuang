"""把引擎包成一个最小 HTTP 服务。

一条命令起服务：

```powershell
python -m harness.cli serve --port 8080
```

端点：

* `GET  /health` —— 是否就绪、预热耗时、累计请求数；
* `POST /check`  —— `{"statement": "...", "proof": "..."}` → 判定；
* `POST /prove`  —— `{"statement": "..."}` → 先试 L0 级联，失败再问模型（可选）。

设计约束：

* **复用同一个常驻 worker**：这是唯一能避开「每次 60 s 载入 Mathlib」的办法；
* 服务是**单线程**的（`HTTPServer`），因为 Lean worker 一次只能处理一个请求；
  并发上来时应该起多个 worker 进程，这不在本版范围。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .cascade import cascade_proof
from .models import Attempt, ModelError, ProposeRequest, build_model
from .problems import Problem
from .worker import LeanWorker, WorkerResult, binder_count, statement_type


def as_problem(statement: str) -> Problem:
    """把用户输入变成 `Problem`。允许只给命题（自动补 `example :`）。"""
    text = statement.strip()
    if not text:
        raise ValueError("statement 为空")
    low = text.lower()
    if not (low.startswith("theorem ") or low.startswith("lemma ") or low.startswith("example")):
        text = f"example : {text}"
    return Problem(problem_id="adhoc", split="Adhoc", header=text, body="")


@dataclass
class ServerStats:
    started_at: float = field(default_factory=time.time)
    warmup_s: float = 0.0
    requests: int = 0
    checks: int = 0
    proofs: int = 0
    solved: int = 0


class ProverService:
    """worker + 可选的模型回路。"""

    def __init__(
        self,
        *,
        worker: LeanWorker | None = None,
        rounds: int = 0,
        allow_network: bool = True,
    ) -> None:
        self.worker = worker or LeanWorker()
        self.rounds = rounds
        self.model = None
        self.model_note = "off"
        if rounds > 0:
            self.model, self.model_note = build_model(allow_network=allow_network)
        self.stats = ServerStats()

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        t0 = time.time()
        self.worker.start()
        self.stats.warmup_s = time.time() - t0

    def stop(self) -> None:
        self.worker.stop()

    # ------------------------------------------------------------------- api
    def _restart(self) -> None:
        """worker 静默崩溃后重启（约 60 s）。"""
        try:
            self.worker.stop()
        except Exception:  # noqa: BLE001
            pass
        self.worker = LeanWorker()
        self.worker.start()

    def check(self, statement: str, proof: str) -> dict[str, Any]:
        p = as_problem(statement)
        try:
            r = self.worker.check(
                statement_type(p.header), proof, nbinders=binder_count(p.header)
            )
        except Exception as exc:  # noqa: BLE001
            self._restart()
            return {"ok": False, "reason": "worker_crash", "error": str(exc)[:300],
                    "goals": -1, "sorry": False, "latency_ms": 0}
        self.stats.checks += 1
        return _check_payload(r)

    def prove(self, statement: str) -> dict[str, Any]:
        p = as_problem(statement)
        stmt_type = statement_type(p.header)
        nb = binder_count(p.header)
        cascade = cascade_proof(deep=False)
        t0 = time.time()

        try:
            r = self.worker.check(stmt_type, cascade, nbinders=nb)
        except Exception as exc:  # noqa: BLE001
            self._restart()
            self.stats.proofs += 1
            return {"ok": False, "proof": None, "stage": "L0", "reason": "worker_crash",
                    "error": str(exc)[:300], "latency_ms": 0, "rounds": 0}
        if r.ok:
            self.stats.proofs += 1
            self.stats.solved += 1
            return {
                "ok": True,
                "proof": cascade,
                "stage": "L0",
                "latency_ms": int((time.time() - t0) * 1000),
                "rounds": 0,
            }

        history: list[Attempt] = [
            Attempt(source="cascade", proof=cascade, status="failed",
                    error_kind=r.reason, diagnostics=r.error[:1000])
        ]
        if self.model is None or self.rounds <= 0:
            self.stats.proofs += 1
            return {
                "ok": False,
                "proof": None,
                "stage": "L0",
                "reason": r.reason,
                "error": r.error[:400],
                "latency_ms": int((time.time() - t0) * 1000),
                "rounds": 0,
            }

        last = r
        for i in range(self.rounds):
            try:
                resp = self.model.propose(
                    ProposeRequest(problem=p, attempt_index=i, history=history)
                )
            except ModelError as exc:
                return {"ok": False, "proof": None, "stage": f"L1#{i + 1}",
                        "reason": f"api_error:{exc.kind}", "error": exc.detail[:300],
                        "latency_ms": int((time.time() - t0) * 1000), "rounds": i}
            last = self.worker.check(stmt_type, resp.proof, nbinders=nb)
            history.append(
                Attempt(source=self.model.name, proof=resp.proof,
                        status="verified" if last.ok else "failed",
                        error_kind=last.reason, diagnostics=last.error[:1000])
            )
            if last.ok:
                self.stats.proofs += 1
                self.stats.solved += 1
                return {
                    "ok": True,
                    "proof": resp.proof,
                    "stage": f"L1#{i + 1}",
                    "latency_ms": int((time.time() - t0) * 1000),
                    "rounds": i + 1,
                    "tokens": {"in": resp.tokens_in, "out": resp.tokens_out},
                }

        self.stats.proofs += 1
        return {
            "ok": False,
            "proof": None,
            "stage": f"L1#{self.rounds}",
            "reason": last.reason,
            "error": last.error[:400],
            "latency_ms": int((time.time() - t0) * 1000),
            "rounds": self.rounds,
        }

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "warmup_s": round(self.stats.warmup_s, 1),
            "uptime_s": round(time.time() - self.stats.started_at, 1),
            "requests": self.stats.requests,
            "checks": self.stats.checks,
            "proofs": self.stats.proofs,
            "solved": self.stats.solved,
            "model": self.model.name if self.model else "off",
            "model_note": self.model_note,
            "rounds": self.rounds,
        }


def _check_payload(r: WorkerResult) -> dict[str, Any]:
    return {
        "ok": r.ok,
        "goals": r.goals,
        "sorry": r.sorry,
        "reason": r.reason,
        "error": r.error[:1000],
        "latency_ms": int(r.latency_ms),
    }


def make_handler(service: ProverService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:  # 安静点
            return

        def do_GET(self) -> None:  # noqa: N802
            service.stats.requests += 1
            if self.path.rstrip("/") in ("", "/health"):
                self._send(200, service.health())
            else:
                self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            service.stats.requests += 1
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}")
            except Exception as exc:  # noqa: BLE001
                self._send(400, {"ok": False, "error": f"bad json: {exc}"})
                return

            path = self.path.rstrip("/")
            try:
                if path == "/check":
                    if not body.get("statement") or not body.get("proof"):
                        self._send(400, {"ok": False, "error": "需要 statement 与 proof"})
                        return
                    self._send(200, service.check(body["statement"], body["proof"]))
                elif path == "/prove":
                    if not body.get("statement"):
                        self._send(400, {"ok": False, "error": "需要 statement"})
                        return
                    self._send(200, service.prove(body["statement"]))
                else:
                    self._send(404, {"ok": False, "error": "not found"})
            except ValueError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"ok": False, "error": f"internal: {exc}"})

    return Handler


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    rounds: int = 0,
    allow_network: bool = True,
    verbose: bool = True,
) -> None:
    """启动 worker 与 HTTP 服务，阻塞直到 Ctrl+C。"""
    service = ProverService(rounds=rounds, allow_network=allow_network)
    if verbose:
        print("启动 worker（首次载入 Mathlib，约 60–240 s）…", flush=True)
    service.start()
    if verbose:
        print(f"就绪：预热 {service.stats.warmup_s:.1f}s，监听 http://{host}:{port}", flush=True)
        print(f"模型：{service.model_note}（rounds={rounds}）", flush=True)

    httpd = HTTPServer((host, port), make_handler(service))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        service.stop()
