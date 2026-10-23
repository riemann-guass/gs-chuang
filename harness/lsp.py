"""常驻 Lean 会话（LSP）客户端。

## 为什么需要它

现在每编译一批题都要重新 `import Mathlib`（约 240 s，见 ADR-0001）。这带来两个后果：

1. 单题交互不可用（`prove()` 一次 4 分钟）；
2. 每一轮 Agent 都要付一次这个成本，多轮 / 多角色时线性放大。

`lean --server` 是 Lean 自带的 LSP 服务：进程常驻，Mathlib 只载入**一次**，
之后每个文件只做增量检查。这是 v0.2 的核心。

## 实现要点

* LSP 消息是 `Content-Length: N\r\n\r\n<json>` 帧；
* 需要处理 server→client 的请求（`workspace/configuration` 等），不回复会卡住；
* 诊断是 `textDocument/publishDiagnostics` 通知，按 URI 收；
* 只实现本项目需要的四个动作：initialize / didOpen / didClose / publishDiagnostics。

线程模型：一个读线程负责分发响应与通知，主线程按 id / URI 等待。
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import config


class LspError(RuntimeError):
    pass


@dataclass
class PublishDiagnostics:
    uri: str
    diagnostics: list[dict] = field(default_factory=list)
    version: int | None = None


class LeanServer:
    """一个常驻的 `lean --server` 进程。"""

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        root_dir: Path | None = None,
        cmd: tuple[str, ...] = ("lake", "env", "lean", "--server"),
        timeout_s: float = 120.0,
    ) -> None:
        #: 子进程的 cwd（决定 `lake env` 提供的 LEAN_PATH）
        self.project_dir = Path(project_dir or config.ENV_PROJECT)
        #: 告诉 server 的 workspace 根（决定模块名解析）。默认与 cwd 相同；
        #: 编译仓库外的文件时必须把 root 指到那个文件所在的工程，否则诊断不落地。
        self.root_dir = Path(root_dir or self.project_dir)
        self.cmd = list(cmd)
        self.timeout_s = timeout_s
        self.proc: subprocess.Popen[bytes] | None = None
        self._next_id = 0
        self._responses: dict[int, queue.Queue] = {}
        self._diag: dict[str, queue.Queue] = {}
        self._progress: dict[str, queue.Queue] = {}
        self._reader: threading.Thread | None = None
        self._alive = False
        self._stderr_tail: list[str] = []

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self.proc is not None:
            return
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.project_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._alive = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        threading.Thread(target=self._stderr_loop, daemon=True).start()

        result = self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": self.root_dir.as_uri(),
                "capabilities": {
                    # 只要诊断；其它能力一律声明为不支持，减少 server 的额外工作
                    "textDocument": {"publishDiagnostics": {"relatedInformation": True}},
                    "workspace": {"configuration": False},
                },
                "workspaceFolders": [
                    {"uri": self.root_dir.as_uri(), "name": self.root_dir.name}
                ],
            },
        )
        if "capabilities" not in result:
            raise LspError(f"initialize 未返回 capabilities：{result}")
        self.notify("initialized", {})

    def stop(self) -> None:
        self._alive = False
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            self.request("shutdown", {}, timeout_s=5.0)
            self.notify("exit", {})
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def __enter__(self) -> "LeanServer":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # ---------------------------------------------------------------- framing
    def _send(self, payload: dict) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise LspError("server 未启动")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        frame = b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        self.proc.stdin.write(frame)
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, *, timeout_s: float | None = None) -> Any:
        self._next_id += 1
        rid = self._next_id
        q: queue.Queue = queue.Queue()
        self._responses[rid] = q
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        try:
            msg = q.get(timeout=timeout_s or self.timeout_s)
        except queue.Empty:
            raise LspError(f"{method} 超时（{timeout_s or self.timeout_s}s）")
        if "error" in msg:
            raise LspError(f"{method} 失败：{msg['error']}")
        return msg.get("result")

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        stream = self.proc.stdout
        while self._alive:
            try:
                length = self._read_header(stream)
                if length is None:
                    break
                body = b""
                while len(body) < length:
                    chunk = stream.read(length - len(body))
                    if not chunk:
                        return
                    body += chunk
                self._dispatch(json.loads(body.decode("utf-8")))
            except Exception:
                break

    @staticmethod
    def _read_header(stream) -> int | None:
        length = None
        while True:
            line = stream.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                return length
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":")[1])

    def _stderr_loop(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for raw in self.proc.stderr:
            if not self._alive:
                break
            try:
                self._stderr_tail.append(raw.decode("utf-8", "replace").rstrip())
                del self._stderr_tail[:-50]
            except Exception:
                pass

    def _dispatch(self, msg: dict) -> None:
        if os.environ.get("DSH_LSP_DEBUG"):
            method = msg.get("method") or ("response" if "id" in msg else "?")
            print(f"[lsp] {method}", file=sys.stderr, flush=True)
        if "id" in msg and "method" not in msg:
            q = self._responses.pop(msg["id"], None)
            if q is not None:
                q.put(msg)
            return
        method = msg.get("method")
        if method == "textDocument/publishDiagnostics":
            params = msg.get("params") or {}
            uri = params.get("uri", "")
            self._diag.setdefault(uri, queue.Queue()).put(
                PublishDiagnostics(
                    uri=uri,
                    diagnostics=params.get("diagnostics") or [],
                    version=params.get("version"),
                )
            )
            return
        if method and method.endswith("/fileProgress"):
            # Lean 用 `processing: [...]` 表示还在分析的区间；空数组 = 这个文件处理完了。
            # **只有看到它归零，publishDiagnostics 才是最终结果**——否则拿到的是
            # didOpen 时那条「先清空」的空诊断（实测踩过）。
            params = msg.get("params") or {}
            uri = params.get("uri", "")
            done = not (params.get("processing") or [])
            self._progress.setdefault(uri, queue.Queue()).put(done)
            return
        if "id" in msg:
            # server → client 的请求：必须回一个合法响应，否则 server 会等
            self._send({"jsonrpc": "2.0", "id": msg["id"], "result": None})

    # ------------------------------------------------------------------- api
    def check_text(self, uri: str, text: str, *, timeout_s: float | None = None) -> list[dict]:
        """打开一个内存文件，**等它真正分析完**，返回最终诊断列表。

        实测事件序列（一个 `import Mathlib` 的文件）：

        ```
        0.0s  fileProgress processing=[1]     ← 开始
        0.3s  publishDiagnostics []           ← 先清空，**这条是空的，不能直接返回**
        39.6s fileProgress processing=[4..1]  ← 载入 Mathlib，区间数变化
        39.6s publishDiagnostics [1 条]       ← 真正的诊断
        39.7s fileProgress processing=[]      ← 处理完成
        ```

        所以必须等到 `processing` 归零，再取最后一版诊断。
        """
        pub_q: queue.Queue = queue.Queue()
        prog_q: queue.Queue = queue.Queue()
        self._diag[uri] = pub_q
        self._progress[uri] = prog_q
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "lean4",
                    "version": 1,
                    "text": text,
                }
            },
        )

        deadline = time.monotonic() + (timeout_s or self.timeout_s)
        latest: list[dict] = []
        finished = False

        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                latest = pub_q.get(timeout=min(0.5, remaining)).diagnostics
            except queue.Empty:
                pass
            try:
                while True:
                    if prog_q.get_nowait():
                        finished = True
            except queue.Empty:
                pass
            if finished:
                # 收尾：把已经排队但还没读的 publish 读掉（它们比空诊断新）
                try:
                    while True:
                        latest = pub_q.get_nowait().diagnostics
                except queue.Empty:
                    pass
                return latest
        raise LspError(f"{uri} 等诊断超时（{timeout_s or self.timeout_s}s）")

    def check_file(self, path: Path, *, timeout_s: float | None = None) -> list[dict]:
        text = Path(path).read_text(encoding="utf-8")
        return self.check_text(Path(path).resolve().as_uri(), text, timeout_s=timeout_s)

    def last_stderr(self) -> str:
        return "\n".join(self._stderr_tail[-10:])
