#!/usr/bin/env python
"""从 L0 运行记录里推出难度分层（家族级）。

用法：
    python scripts/difficulty_report.py runs/m1-valid244b.jsonl

产出：`docs/research/difficulty.json`，形如

    {"tiers": {"easy": [...], "medium": [...], "hard": [...]},
     "families": {"mathd_algebra": {"total": 70, "verified": 3, "pass@1": 0.043, "tier": "medium"}},
     ...}

## 方法

按家族算 pass@1，把家族从难到易排序，再按**题目数**三等分：题目数累计约 1/3 的
家族为 `easy`（最容易的那批），末尾 1/3 为 `hard`，中间为 `medium`。
用题目数而不是家族数分箱，是因为家族大小差得很远（`mathd_algebra` 70 题、
`aimeII` 2 题）。

## 重要警告

这些分层是**从 L0 自己的结果推出来的**，因此：

* **不能**用它们再去评价 L0 —— 那就是循环论证；
* 它们的用途是给**后续实验**（M2/M3 的对照）挑规模相当、难度可比的子集；
* 家族内部方差很大（`mathd_algebra` 里既有 `norm_num` 秒解的也有难题），
  所以这是**粗分层**，不是单题难度标签。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config, metrics  # noqa: E402
from harness.problems import family_of  # noqa: E402

CAVEAT = (
    "分层由 L0 自身的家族 pass@1 推出，不能用于评价 L0（循环论证）；"
    "只用于给后续实验挑规模相当的子集。家族内方差大，属粗分层。"
)


def assign_tiers(rows: list[dict], overall: float) -> dict[str, list[str]]:
    """按家族 pass@1 相对总体水平分三档。

    试过「按题目数三等分」，结果是 `mathd_algebra`（24.3%）也被塞进 `easy`——
    因为两个大家族一加就超过 1/3 了。改成相对阈值后含义更清楚：

    * `easy`：pass@1 ≥ 2 × 总体（L0 明显做得动的）
    * `hard`：pass@1 = 0（L0 一题都没做出来的）
    * `medium`：其余

    三个集合互斥且覆盖全部家族；阈值直接可解释，不用再解释「为什么这个算中档」。
    """
    tiers: dict[str, list[str]] = {"easy": [], "medium": [], "hard": []}
    easy_cut = 2 * overall
    for row in rows:
        if row["pass@1"] > 0 and row["pass@1"] >= easy_cut:
            tiers["easy"].append(row["family"])
        elif row["pass@1"] == 0:
            tiers["hard"].append(row["family"])
        else:
            tiers["medium"].append(row["family"])
    return tiers


def main() -> int:
    ap = argparse.ArgumentParser(description="从 L0 记录推出家族级难度分层")
    ap.add_argument("run", help="JSONL 运行记录")
    ap.add_argument("--out", default=str(config.REPO_ROOT / "docs" / "research" / "difficulty.json"))
    args = ap.parse_args()

    run_path = Path(args.run)
    records = metrics.load_jsonl(run_path)
    summary = metrics.summarize(records)
    fam = summary.by_family()

    rows = [
        {"family": f, "total": v["total"], "verified": v["verified"], "pass@1": v["pass@1"]}
        for f, v in fam.items()
    ]
    tiers = assign_tiers(rows, summary.pass_at_1)
    tier_of = {f: t for t, fams in tiers.items() for f in fams}
    for r in rows:
        r["tier"] = tier_of.get(r["family"], "hard")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_run": str(run_path),
        "ladder_version": next(
            (r.get("ladder_version") for r in records if r.get("ladder_version")), config.LADDER_VERSION
        ),
        "lean_toolchain": config.LEAN_TOOLCHAIN,
        "mathlib_rev": config.MATHLIB_REV,
        "overall": {
            "total": summary.total,
            "verified": summary.verified,
            "pass@1": round(summary.pass_at_1, 4),
        },
        "tiers": tiers,
        "families": {r["family"]: r for r in rows},
        "caveat": CAVEAT,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"总体 pass@1 = {summary.verified}/{summary.total} = {summary.pass_at_1:.2%}")
    print(f"{'家族':<20}{'题数':>5}{'通过':>6}{'pass@1':>9}  档位")
    for r in rows:
        print(f"{r['family']:<20}{r['total']:>5}{r['verified']:>6}{r['pass@1']:>9.1%}  {r['tier']}")
    print(f"\n写出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
