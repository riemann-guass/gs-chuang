"""Lean 编译后端。

## 为什么是「批量编译」

实测（2026-10-19，本机）：

| 场景 | 耗时 |
|---|---|
| `import Mathlib.Algebra.Group.Defs` | ~10 s |
| `import Mathlib`（单题） | 230–260 s |
| `import Mathlib` + 同一个文件里 4 道题 | 242 s |

也就是说成本几乎完全由 `import Mathlib`（加载 ~7500 个 olean）决定，
与文件里有几道题**无关**。所以把同一轮所有待证题拼进一个文件，
可以把 N 道题的成本压到 1 次。

代价是：一道题的语法错误可能影响同文件的其它题。实测 Lean 会继续
elaborate 后续声明（probe2 中失败的 t2 之后的 t3/t4 仍然正常处理），
所以按行号把诊断映射回题目是可行的。
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from . import config

#: 488 道 miniF2F 题文件共有的前缀，扫描确认 100% 一致。
def build_preamble(extra_options: Sequence[str] = ()) -> str:
    """构造批次文件的前缀。

    `extra_options` 用来做「确定性补救」实验：例如级联因 `max_rec_depth` 失败时，
    用 `["maxRecDepth=10000", "exponentiation.threshold=10000"]` 重跑同一批 tactic，
    **不需要模型**。见 `docs/research/m3-hints-ab.md`。
    """
    lines = [
        "import Mathlib",
        "",
        f"set_option maxHeartbeats {config.MAX_HEARTBEATS}",
        # 级联用 `first` 写成一整条，Lean 会对未执行的分支报 unreachableTactic，
        # 这些是预期噪音，关掉以免污染诊断文本。
        "set_option linter.unreachableTactic false",
        "set_option linter.unusedTactic false",
    ]
    for opt in extra_options:
        # 命令行习惯写 `name=value`，但 Lean 的语法是 `set_option name value`
        lines.append(f"set_option {opt.replace('=', ' ', 1)}")
    lines += ["", "open BigOperators Real Nat Topology Rat", ""]
    return "\n".join(lines) + "\n"


#: 默认前缀（无额外 option），保持与历史运行一致
PREAMBLE = build_preamble()


class LeanEnvError(RuntimeError):
    """编译环境不可用（工程缺失、toolchain 不匹配等）。"""


@dataclass(frozen=True)
class BatchItem:
    """一道题在批量文件中的一段。

    `header` 是定理声明中 `:= by` **之前**的部分（含 `theorem` 关键字与名字），
    `proof` 是 `:= by` **之后**的 tactic 文本。
    """

    problem_id: str
    header: str
    proof: str


@dataclass(frozen=True)
class Span:
    """题目在批量文件里占用的行区间（1-based，闭区间）。"""

    first_line: int
    last_line: int
    axioms_line: int

    def contains(self, line: int) -> bool:
        return self.first_line <= line <= self.last_line


@dataclass(frozen=True)
class RenderedBatch:
    text: str
    spans: dict[str, Span]
    path: Path
    #: problem_id -> 该题在文件里的全限定定理名
    qualified_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompileResult:
    returncode: int
    output: str
    duration_ms: int
    path: Path


def _indent(text: str, prefix: str = "  ") -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # 去掉尾部空行，避免在文件里留下裸缩进
    while lines and not lines[-1].strip():
        lines.pop()
    out: list[str] = []
    for line in lines:
        out.append(prefix + line if line.strip() else "")
    return out


def render_batch(
    items: Sequence[BatchItem], path: Path, *, extra_options: Sequence[str] = ()
) -> RenderedBatch:
    """把若干题目渲染成一个 Lean 文件，并记录每题的 span。"""
    if not items:
        raise ValueError("render_batch 收到 0 道题")

    lines: list[str] = build_preamble(extra_options).rstrip("\n").split("\n")
    lines.append("")

    spans: dict[str, Span] = {}
    qualified: dict[str, str] = {}

    for idx, item in enumerate(items):
        ns = f"M{idx:04d}"
        lines.append(f"namespace {ns}")
        start = len(lines) + 1  # 即将写入的 theorem 行（1-based）

        header_lines = item.header.strip().split("\n")
        # `:= by` 必须接在 header 的**最后一行**：多行声明（参数换行）时
        # 接在第一行会得到 `... : := by`，Lean 报 "unexpected token ':='; expected term"。
        for cont in header_lines[:-1]:
            lines.append(cont.rstrip())
        lines.append(header_lines[-1].strip() + " := by")
        body = _indent(item.proof)
        if body:
            lines.extend(body)
        else:
            lines.append("  sorry")
        name = item.header.split()[1]
        axiom_line = len(lines) + 1
        lines.append(f"#print axioms {ns}.{name}")
        lines.append(f"end {ns}")
        end = len(lines)

        spans[item.problem_id] = Span(start, end, axiom_line)
        qualified[item.problem_id] = f"{ns}.{name}"

    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return RenderedBatch(text=text, spans=spans, path=path, qualified_names=qualified)


def check_env() -> None:
    """编译环境自检：工程目录与 Mathlib 根模块都要在。"""
    project = config.ENV_PROJECT
    if not project.is_dir():
        raise LeanEnvError(f"编译工程不存在：{project}")
    root_olean = project / ".lake" / "packages" / "mathlib" / ".lake" / "build" / "lib" / "lean" / "Mathlib.olean"
    if not root_olean.is_file():
        raise LeanEnvError(
            "找不到 Mathlib 根模块，`import Mathlib` 不可能成功：\n"
            f"  {root_olean}\n"
            "本机只有 sgslean 那份 Mathlib 是完整构建，见 ADR-0001。"
        )


def lean_argv(path: Path) -> list[str]:
    """编译一个文件的完整命令行。

    `-DmaxErrors=0` 是必须的：Lean 默认攒够 **100 个错误就直接退出**，后面的声明
    根本不会被处理。批量编译里这等于「一道题出错，后面几十题全被吞掉」——
    实测 244 题单批次恰好停在 ~110 题，就是这么来的（ADR-0004）。

    注意：写在文件里的 `set_option maxErrors 0` **无效**，只有命令行 `-D` 才管用
    （实测两种写法对比：`set_option` 仍停在 101 条错误，`-DmaxErrors=0` 报满 120 条）。
    """
    return ["lake", "env", "lean", "-DmaxErrors=0", str(path)]


def compile_file(path: Path, *, timeout_s: int | None = None) -> CompileResult:
    """用承载工程的环境编译一个 Lean 文件。

    墙钟超时是**唯一的硬兜底**：模型生成的证明里可能混进跑不完的 tactic，
    超时后返回 `returncode=-1`，由调用方标成 `batch_timeout`，而不是让整轮挂死。
    """
    check_env()
    timeout = timeout_s or config.COMPILE_TIMEOUT_S
    started = time.monotonic()
    try:
        proc = subprocess.run(
            lean_argv(path),
            cwd=str(config.ENV_PROJECT),
            capture_output=True,
            timeout=timeout,
            # Lean 输出是 UTF-8；Windows 控制台默认 GBK，必须显式指定
            encoding="utf-8",
            errors="replace",
        )
        returncode = proc.returncode
        output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        returncode = -1
        partial = exc.stdout or exc.stderr or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        output = f"[harness] 编译超时（{timeout} s），已中止\n{partial}"
    duration_ms = int((time.monotonic() - started) * 1000)
    return CompileResult(
        returncode=returncode,
        output=output,
        duration_ms=duration_ms,
        path=path,
    )


def compile_items(
    items: Sequence[BatchItem],
    *,
    work_name: str,
    timeout_s: int | None = None,
    log_dir: Path | None = None,
    extra_options: Sequence[str] = (),
) -> tuple[RenderedBatch, CompileResult]:
    batch = render_batch(items, config.WORK_DIR / f"{work_name}.lean", extra_options=extra_options)
    result = compile_file(batch.path, timeout_s=timeout_s)
    if log_dir is not None:
        # 保留原始编译器输出：批量编译一旦中途中断，没有日志就无法定位是第几题
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{work_name}.lean.log").write_text(result.output, encoding="utf-8", newline="\n")
    return batch, result


def write_single(problem_id: str, header: str, proof: str, path: Path) -> Path:
    """把单道题写成独立文件（调试用，成本等同一次完整 Mathlib 载入）。"""
    text = PREAMBLE + "\n".join([f"{header.strip()} := by", *_indent(proof)]) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
