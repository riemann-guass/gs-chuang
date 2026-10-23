"""常驻 Lean worker 的 Python 客户端。

## 为什么用文件协议

`run_tac` 里的 `IO.getStdin` 在 `lean file.lean` 下永远拿到 EOF（实测 `len=0`），
所以 stdin/stdout 不能用来通信；而且 Lean 自己会把诊断写到 stdout，会污染协议。
于是双方只通过目录里的文件对话：

* 客户端写 `req_<seq>.json`，worker 轮询到后写出 `resp_<seq>.json`；
* 轮询间隔 25 ms，实测单条往返 50–125 ms。

## 为什么值

* 批量编译：每次 `import Mathlib` 约 60–240 s，**每题都付**；
* worker：导入一次（实测 65 s），之后每题 **0.05–0.13 s**。

## 用法

```python
with LeanWorker() as w:                 # 启动并预热（约 65 s）
    r = w.check("(1:Nat) + 1 = 2", "norm_num")
    assert r.ok
```
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import config

#: worker 的源码位置（相对本仓库）
WORKER_FILE = "Worker.lean"


class WorkerError(RuntimeError):
    pass


def classify_worker_error(message: str) -> str:
    """把 worker 回传的错误文本归成和批量编译一致的类别。

    类别名对齐 `harness.diagnostics.classify` 的取值，方便两边统计口径一致。
    """
    m = (message or "").lower()
    if not m:
        return "none"
    if "cascade_exhausted" in m:
        return "cascade_exhausted"
    if "unsolved" in m:
        return "unsolved_goals"
    if "type mismatch" in m:
        return "type_mismatch"
    if "unknown identifier" in m or "unknown constant" in m or "unknown module" in m:
        return "unknown_ident"
    if "maximum recursion depth" in m:
        return "max_rec_depth"
    if "heartbeats" in m:
        return "heartbeat_limit"
    if "did not find" in m or "failed" in m or "error" in m:
        return "tactic_error"
    return "other"


@dataclass
class WorkerResult:
    ok: bool
    goals: int = -1
    sorry: bool = False
    error: str = ""
    latency_ms: float = 0.0
    raw: dict = field(default_factory=dict)

    @property
    def reason(self) -> str:
        if self.ok:
            return "ok"
        if self.sorry:
            return "sorry"
        if self.goals > 0:
            return "unsolved_goals"
        return classify_worker_error(self.error)


def statement_type(header: str) -> str:
    """把 `theorem name binders : type` 变成可直接 elaborate 的命题 `∀ binders, type`。

    顶层的 `:` 用括号深度扫描找，避免被 `(n : Nat)` 里的冒号误导。
    """
    binders, prop = _split_header(header)
    return f"∀ {binders}, {prop}" if binders else prop


def binder_count(header: str) -> int:
    """数定理头部引入了几个**变量**（不是几个括号组）。

    `(a b : ℂ)` 是 2 个变量、`{n : Nat}` 是 1 个、`[Group G]`（实例绑定）是 1 个。
    worker 要按这个数把绑定逐个引进局部上下文，才能和声明形状一致。
    """
    binders, _ = _split_header(header)
    total = 0
    depth = 0
    start = -1
    for i, ch in enumerate(binders):
        if ch in "([{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0 and start >= 0:
                inner = binders[start:i]
                total += _vars_in_group(inner)
                start = -1
    return total


def _vars_in_group(inner: str) -> int:
    """`a b : ℂ` → 2；`Group G`（实例绑定，无冒号）→ 1。"""
    depth = 0
    for i, ch in enumerate(inner):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            return max(1, len(inner[:i].split()))
    return 1


def _split_header(header: str) -> tuple[str, str]:
    text = header.strip()
    for kw in ("theorem ", "lemma ", "example"):
        if text.startswith(kw):
            text = text[len(kw) :].strip()
            break
    else:
        raise ValueError(f"不是定理语句：{header[:40]!r}")

    if text.startswith(":"):  # `example : P`
        return "", text[1:].strip()

    depth = 0
    colon = -1
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            colon = i
            break
    if colon < 0:
        raise ValueError(f"找不到类型分隔符：{header[:60]!r}")

    head, prop = text[:colon], text[colon + 1 :].strip()
    parts = head.split(None, 1)
    binders = parts[1].strip() if len(parts) > 1 else ""
    return binders, prop


class LeanWorker:
    """一个常驻的 `lean Worker.lean` 进程。"""

    def __init__(
        self,
        *,
        work_dir: Path | None = None,
        startup_timeout_s: float = 900.0,
        request_timeout_s: float = 120.0,
        poll_s: float = 0.02,
        lean_dir: Path | None = None,
    ) -> None:
        self.lean_dir = Path(lean_dir or config.LEAN_ROOT)
        # 默认放进工作区（`lean/Bench/_work/_worker`）：系统临时目录在沙箱下可能不可写，
        # 而且放在仓库里便于事后看请求/响应文件。
        if work_dir is None:
            self.work_dir = Path(config.WORK_DIR) / "_worker"
            self._owns_dir = False
        else:
            self.work_dir = Path(work_dir)
            self._owns_dir = False
        self.startup_timeout_s = startup_timeout_s
        self.request_timeout_s = request_timeout_s
        self.poll_s = poll_s
        self.proc: subprocess.Popen[bytes] | None = None
        self._seq = 0
        self.warmup_s: float = 0.0

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for old in self.work_dir.glob("req_*"):
            old.unlink(missing_ok=True)
        for old in self.work_dir.glob("rsp_*"):
            old.unlink(missing_ok=True)
        env = dict(os.environ)
        env["WORKER_DIR"] = str(self.work_dir)
        env.setdefault("ELAN_HOME", str(Path.home() / ".elan"))
        # 把 Lean 自己的输出落到文件：崩溃时这是唯一的线索
        self._out = open(self.work_dir / "lean.out", "w", encoding="utf-8", errors="replace")
        self._err = open(self.work_dir / "lean.err", "w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            ["lake", "env", "lean", WORKER_FILE],
            cwd=str(self.lean_dir),
            env=env,
            stdout=self._out,
            stderr=self._err,
        )
        t0 = time.time()
        probe = self._request({"id": "warmup", "type": "(1 : Nat) = 1", "proof": "rfl"},
                              timeout_s=self.startup_timeout_s)
        if probe is None or not probe.get("ok"):
            self.stop()
            raise WorkerError(f"worker 预热失败：{probe}")
        self.warmup_s = time.time() - t0

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is not None:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        if self._owns_dir:
            shutil.rmtree(self.work_dir, ignore_errors=True)

    def __enter__(self) -> "LeanWorker":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # ------------------------------------------------------------------- api
    def check(
        self, prop: str, proof: str, *, nbinders: int = 0, timeout_s: float | None = None
    ) -> WorkerResult:
        """判定 `proof` 是否闭合了命题 `prop`。

        `nbinders` 是定理参数个数：worker 会先把它引进局部上下文再证明，
        这样目标和批量编译里的声明形状一致。
        """
        t0 = time.time()
        resp = self._request(
            # nbinders 用字符串传：Lean 侧统一按字符串读字段，数字会被读成空
            {"id": f"r{self._seq}", "type": prop, "proof": proof, "nbinders": str(nbinders)},
            timeout_s=timeout_s or self.request_timeout_s,
        )
        if resp is None:
            raise WorkerError(f"worker 无响应（可能已崩溃）\n{self.tail_log()}")
        return WorkerResult(
            ok=bool(resp.get("ok")),
            goals=int(resp.get("goals", -1)),
            sorry=bool(resp.get("sorry")),
            error=str(resp.get("error", "")),
            latency_ms=(time.time() - t0) * 1000,
            raw=resp,
        )

    def check_problem(self, problem, proof: str) -> WorkerResult:
        """直接吃一个 `Problem`（从 header 推出命题与参数个数）。"""
        return self.check(
            statement_type(problem.header), proof, nbinders=binder_count(problem.header)
        )

    # --------------------------------------------------------------- private
    def tail_log(self, n: int = 15) -> str:
        """崩溃时把 Lean 的最后几行输出带出来，否则完全没法定位。"""
        lines: list[str] = []
        for name in ("lean.err", "lean.out"):
            path = self.work_dir / name
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace").strip()
                except OSError:
                    continue
                if text:
                    lines.extend(text.splitlines()[-n:])
        return "\n".join(lines)

    def _request(self, payload: dict, *, timeout_s: float) -> dict | None:
        if self.proc is None:
            raise WorkerError("worker 未启动")
        self._seq += 1
        name = f"{self._seq:06d}"
        # 文件名纯 ASCII、无扩展名：Lean 侧避免任何字符串切片操作
        req = self.work_dir / f"req_{name}"
        resp = self.work_dir / f"rsp_{name}"
        # ensure_ascii：让协议字节流保持纯 ASCII，绕开 Lean 的多字节切片 panic
        req.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if resp.exists():
                try:
                    text = resp.read_text(encoding="utf-8").strip()
                except OSError:
                    text = ""
                if text:
                    return json.loads(text)
            if self.proc.poll() is not None:
                return None
            time.sleep(self.poll_s)
        return None
