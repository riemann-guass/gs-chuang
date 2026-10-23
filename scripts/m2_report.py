#!/usr/bin/env python
"""从一次 cascade+模型 运行里生成 M2 对照报告。

    python scripts/m2_report.py runs/m2-real3.jsonl

输出：
1. 第 0 轮纯级联 vs 最终（同一次运行、同一环境，见 metrics.cascade_baseline）
2. 模型补足 / 弄坏的题目清单
3. 模型各轮尝试的失败类型分布
4. token 与耗时
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import metrics  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 对照报告")
    ap.add_argument("run")
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()

    records = metrics.load_jsonl(Path(args.run))
    base = metrics.cascade_baseline(records)
    final = metrics.summarize(records)
    n = len(records)

    gained = [
        r["problem_id"]
        for r in records
        if r["status"] == "verified" and (not r["attempts"] or r["attempts"][0].get("status") != "verified")
    ]
    lost = [
        r["problem_id"]
        for r in records
        if r["status"] != "verified" and r["attempts"] and r["attempts"][0].get("status") == "verified"
    ]

    print(f"题数 {n}   model = {records[0].get('model')}")
    print(f"  第 0 轮纯级联   {base['verified']:3d}/{n} = {base['pass@1']:.2%}")
    print(f"  最终（含模型）   {final.verified:3d}/{n} = {final.pass_at_1:.2%}   "
          f"净变化 {final.verified - base['verified']:+d} 题")
    print(f"  模型补足 {len(gained)} 题，模型弄坏 {len(lost)} 题")

    # 模型各轮尝试的失败类型
    kinds: Counter = Counter()
    rounds: Counter = Counter()
    empty = 0
    for r in records:
        for a in r.get("attempts", [])[1:]:
            rounds[a.get("round")] += 1
            kinds[a.get("error_kind", "?")] += 1
            if not (a.get("proof") or "").strip():
                empty += 1
    print(f"\n模型尝试 {sum(rounds.values())} 次，轮次分布 {dict(sorted(rounds.items()))}")
    print(f"  空 proof {empty} 次")
    print(f"  失败类型 {dict(kinds.most_common())}")

    tin = sum(int(r.get("tokens_in", 0)) for r in records)
    tout = sum(int(r.get("tokens_out", 0)) for r in records)
    calls = sum(rounds.values())
    print(f"\ntoken in={tin} out={tout}  共 {calls} 次调用，平均每次 in {tin / max(calls, 1):.0f} / out {tout / max(calls, 1):.0f}")

    if gained:
        print(f"\n模型补足（前 {args.show}）:")
        for p in gained[: args.show]:
            print("  +", p)
    if lost:
        print(f"\n模型弄坏（前 {args.show}）:")
        for p in lost[: args.show]:
            print("  -", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
