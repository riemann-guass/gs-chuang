#!/usr/bin/env python
"""并排比较两次运行（例如「纯级联」vs「级联 + 模型」）。

    python scripts/compare_runs.py runs/m1-valid244b.jsonl runs/m2-real.jsonl

只看两次运行**共同覆盖**的题目，避免拿不同子集比来比去。
输出四格：两边都过 / 只有 A 过 / 只有 B 过 / 都没过，以及 token 与时间。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import metrics  # noqa: E402


def load(path: Path) -> dict[str, dict]:
    return {r["problem_id"]: r for r in metrics.load_jsonl(path)}


def main() -> int:
    ap = argparse.ArgumentParser(description="比较两次运行")
    ap.add_argument("a", help="基线 JSONL，例如纯级联")
    ap.add_argument("b", help="对照 JSONL，例如 cascade + 模型")
    ap.add_argument("--show", type=int, default=10, help="最多列出多少条差异题")
    args = ap.parse_args()

    a = load(Path(args.a))
    b = load(Path(args.b))
    common = sorted(set(a) & set(b))
    if not common:
        print("两次运行没有共同题目，无法比较", file=sys.stderr)
        return 2

    both = [p for p in common if a[p]["status"] == "verified" and b[p]["status"] == "verified"]
    only_a = [p for p in common if a[p]["status"] == "verified" and b[p]["status"] != "verified"]
    only_b = [p for p in common if a[p]["status"] != "verified" and b[p]["status"] == "verified"]
    neither = [p for p in common if a[p]["status"] != "verified" and b[p]["status"] != "verified"]

    n = len(common)
    print(f"共同题目 {n}")
    print(f"  两边都过      {len(both):3d}  ({len(both) / n:.1%})")
    print(f"  只有基线上过  {len(only_a):3d}  ({len(only_a) / n:.1%})  ← 模型弄坏的")
    print(f"  只有对照上过  {len(only_b):3d}  ({len(only_b) / n:.1%})  ← 模型补足的")
    print(f"  都没过        {len(neither):3d}  ({len(neither) / n:.1%})")
    print()
    print(f"pass@1  基线 {len(both) + len(only_a)}/{n} = {(len(both) + len(only_a)) / n:.2%}"
          f"   对照 {len(both) + len(only_b)}/{n} = {(len(both) + len(only_b)) / n:.2%}")

    tin = sum(int(b[p].get("tokens_in", 0)) for p in common)
    tout = sum(int(b[p].get("tokens_out", 0)) for p in common)
    rounds = [len(b[p].get("attempts", [])) for p in common]
    print(f"token   in={tin} out={tout}  平均每题输入 {tin / n:.0f}")
    print(f"尝试次数分布 {dict(sorted(__import__('collections').Counter(rounds).items()))}")

    if only_b and args.show:
        print(f"\n模型补足的题（前 {args.show} 个）:")
        for p in only_b[: args.show]:
            print("  +", p)
    if only_a and args.show:
        print(f"\n模型弄坏的题（前 {args.show} 个）:")
        for p in only_a[: args.show]:
            print("  -", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
