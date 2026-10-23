#!/usr/bin/env python
"""miniF2F × 本机 Lean/Mathlib 版本兼容性扫描。

背景：miniF2F 上游 `lean-toolchain` 声明的是 **v4.24.0**，而本机唯一完整的
Mathlib 构建是 **v4.28.0-rc1**（见 ADR-0001）。Mathlib 的 API 会随版本变动，
所以必须知道**哪些题的语句在当前版本下根本编译不过** —— 这些题不是「证明失败」，
而是「题目失效」，在统计正确率时必须排除，否则会低估系统。

做法：把全部 488 道题的语句（证明体统一填 `sorry`）拼成一个文件编译一次。
`sorry` 的告警是预期的，只看 `error` 级诊断。

用法：
    python scripts/compat_scan.py
    python scripts/compat_scan.py --split Valid
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config, diagnostics, leanenv  # noqa: E402
from harness.problems import Problem, family_of, load_index  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描 miniF2F 与本机 Lean/Mathlib 的兼容性")
    ap.add_argument("--split", default="all", choices=["all", "Valid", "Test"])
    ap.add_argument("--out", default="", help="JSON 结果路径")
    args = ap.parse_args()

    config.ensure_dirs()
    problems: list[Problem] = load_index()
    if args.split != "all":
        problems = [p for p in problems if p.split == args.split]
    print(f"题目 {len(problems)} 道；编译一次（Mathlib 载入约 4 分钟）…", flush=True)

    items = [p.item("sorry") for p in problems]
    batch, result = leanenv.compile_items(items, work_name="compat-scan")
    parsed = diagnostics.parse(result.output)
    per_problem = diagnostics.locate_spans(parsed.diagnostics, batch.spans)

    broken: list[dict] = []
    ok_by_split: Counter = Counter()
    bad_by_split: Counter = Counter()
    bad_by_family: Counter = Counter()

    for p in problems:
        errs = [d for d in per_problem.get(p.problem_id, []) if d.severity == "error"]
        if errs:
            broken.append(
                {
                    "id": p.problem_id,
                    "split": p.split,
                    "family": family_of(p.problem_id),
                    "kind": diagnostics.classify(errs),
                    "message": errs[0].message,
                    "detail": errs[0].detail[:800],
                }
            )
            bad_by_split[p.split] += 1
            bad_by_family[family_of(p.problem_id)] += 1
        else:
            ok_by_split[p.split] += 1

    total_ok = sum(ok_by_split.values())
    print("\n=== 结果 ===")
    print(f"可编译   {total_ok}/{len(problems)}  ({total_ok / max(len(problems), 1):.2%})")
    for split in sorted(set(ok_by_split) | set(bad_by_split)):
        print(f"  {split:5s}  ok={ok_by_split.get(split, 0):3d}  broken={bad_by_split.get(split, 0):3d}")
    if bad_by_family:
        print("  失效家族分布：", dict(sorted(bad_by_family.items(), key=lambda kv: -kv[1])))
    if broken:
        print(f"\n前 15 个失效题目：")
        for b in broken[:15]:
            print(f"  [{b['split']}] {b['id']:<46} {b['kind']:<18} {b['message'][:80]}")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "lean_toolchain": config.LEAN_TOOLCHAIN,
        "mathlib_rev": config.MATHLIB_REV,
        "total": len(problems),
        "compilable": total_ok,
        "broken": broken,
        "ok_by_split": dict(ok_by_split),
        "bad_by_split": dict(bad_by_split),
        "compile_ms": result.duration_ms,
    }
    out = Path(args.out) if args.out else (config.RUNS_DIR / "compat-scan.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {out}（编译 {result.duration_ms / 1000:.0f} s）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
