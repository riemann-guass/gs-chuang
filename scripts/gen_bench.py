#!/usr/bin/env python
"""从 miniF2F 上游 checkout 生成本仓库的 bench 目录。

用法：

    python scripts/gen_bench.py
    python scripts/gen_bench.py --source "D:\\path\\to\\miniF2F-lean4"

产物（全部是派生物，已 gitignore）：

    lean/Bench/Valid/<id>.lean
    lean/Bench/Test/<id>.lean
    lean/Bench/index.jsonl

题目文件**原样复制**，不重新渲染 —— 保证定理语句与上游逐字一致。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config  # noqa: E402
from harness.problems import parse_problem_text  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 lean/Bench 目录")
    ap.add_argument("--source", default=str(config.RAW_MINI2F), help="miniF2F-lean4 仓库根目录")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        print(f"[错误] 源目录不存在：{source}", file=sys.stderr)
        return 2

    config.BENCH_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for split in ("Valid", "Test"):
        src_dir = source / "MiniF2F" / split
        if not src_dir.is_dir():
            print(f"[错误] 缺少 {src_dir}", file=sys.stderr)
            return 2
        dst_dir = config.BENCH_DIR / split
        dst_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(src_dir.glob("*.lean"))
        kept = 0
        for src in files:
            text = src.read_text(encoding="utf-8")
            header, _body = parse_problem_text(text)  # 校验可解析，顺带取定理名
            name = header.split()[1]
            dst = dst_dir / src.name
            if args.force or not dst.exists():
                shutil.copyfile(src, dst)
            rows.append(
                {
                    "id": src.stem,
                    "split": split,
                    "theorem": name,
                    "file": f"{split}/{src.name}",
                    "statement_sha256": "sha256:"
                    + hashlib.sha256(header.encode("utf-8")).hexdigest()[:16],
                }
            )
            kept += 1
        print(f"{split:5s}  {kept} 题")

    with config.INDEX_FILE.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"写出 {config.INDEX_FILE}（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
