"""题目读取与文本切分。

miniF2F 的单题文件结构 100% 一致（扫描 488 个文件确认）：

```
import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

theorem <name> <参数与命题> := by sorry
```

因此可以用固定的切分规则：找到第一个 `theorem`，再找 `:= by`，
左边是 `header`（含 `theorem` 与名字），右边是证明体。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .leanenv import BatchItem

_THEOREM_RE = re.compile(r"^theorem\s+", re.M)
_NAME_RE = re.compile(r"^theorem\s+([^\s(]+)")


def family_of(problem_id: str) -> str:
    """粗粒度家族名，例如 `mathd_algebra`、`induction`、`amc12a`。

    miniF2F 的 id 形如 `mathd_algebra_10` / `amc12a_2002_p1` / `induction_sum_odd`，
    `mathd_*` 取前两段合起来作为家族；其余取第一段。
    """
    parts = problem_id.split("_")
    head = parts[0]
    if head == "mathd" and len(parts) > 1:
        return f"mathd_{parts[1]}"
    return head


@dataclass(frozen=True)
class Problem:
    problem_id: str
    split: str
    header: str
    body: str
    source_file: str = ""

    @property
    def name(self) -> str:
        m = _NAME_RE.match(self.header)
        if not m:
            raise ValueError(f"无法从 header 里取出定理名：{self.header[:80]!r}")
        return m.group(1)

    def item(self, proof: str) -> BatchItem:
        return BatchItem(problem_id=self.problem_id, header=self.header, proof=proof)


def parse_problem_text(text: str) -> tuple[str, str]:
    """返回 `(header, body)`；`header` 不含 `:= by`。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = _THEOREM_RE.search(text)
    if not m:
        raise ValueError("文件里没有 theorem 声明")
    tail = text[m.start():]
    idx = tail.find(":= by")
    if idx < 0:
        raise ValueError("定理声明里没有 ':= by'")
    header = tail[:idx].strip()
    body = tail[idx + len(":= by"):].strip()
    if not _NAME_RE.match(header):
        raise ValueError(f"不认识的 header：{header[:80]!r}")
    return header, body


def load_problem_file(path: Path, *, split: str) -> Problem:
    header, body = parse_problem_text(path.read_text(encoding="utf-8"))
    return Problem(problem_id=path.stem, split=split, header=header, body=body, source_file=str(path))


def statement_sha(problem: Problem) -> str:
    return "sha256:" + hashlib.sha256(problem.header.encode("utf-8")).hexdigest()[:16]


def load_index() -> list[Problem]:
    """读取 `lean/Bench/index.jsonl`。"""
    if not config.INDEX_FILE.is_file():
        raise FileNotFoundError(
            f"缺少 {config.INDEX_FILE}，先运行 `python scripts/gen_bench.py`"
        )
    problems: list[Problem] = []
    with config.INDEX_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            path = config.BENCH_DIR / row["split"] / f"{row['id']}.lean"
            problems.append(load_problem_file(path, split=row["split"]))
    return problems


def load_proposal_problems() -> list[Problem]:
    """拿全部 Test 题（严格说只用于最终评测）。"""
    return [p for p in load_index() if p.split == "Test"]
