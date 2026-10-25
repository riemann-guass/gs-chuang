"""P2-pre 探针：Flash 到底会不会选策略？

在实现 Strategist 之前先花 244 次调用回答这个问题（计划里的可证伪实验 #2）：

* 让模型对每题输出「最可能的策略 + 置信度」；
* 用**已解出题目的最终证明**做弱标签（关键词：`by_contra`/`exfalso` → 反证，
  `induction` → 归纳，`rcases`/`by_cases` → 分类讨论……）；
* 算 top-1 命中率。

判据：< 60% → 策略标签噪声太大，跳过 Strategist；> 80% → 不加角色，直接做路由。

用法：
    python scripts/strategy_probe.py --run runs/v0.5-baseline.jsonl --limit 244
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import roles  # noqa: E402
from harness.models import ModelError, ProposeRequest, build_model  # noqa: E402
from harness.problems import load_index  # noqa: E402

#: 从最终证明里抽「实际用了什么策略」的弱标签
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("contradiction", ("by_contra", "exfalso", "absurd", "contrapose")),
    ("induction", ("induction ", "Nat.rec", "induction'")),
    ("cases", ("rcases", "by_cases", "obtain", "cases ")),
    ("construction", ("use ", "refine ⟨", "constructor")),
    ("direct", ("simp", "norm_num", "ring", "linarith", "nlinarith", "omega", "rfl", "exact")),
]


def actual_strategy(proof: str) -> str:
    """按关键词给最终证明打一个弱标签（顺序即优先级）。"""
    low = (proof or "").lower()
    for label, words in KEYWORDS:
        if any(w.lower() in low for w in words):
            return label
    return "other"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/v0.5-baseline.jsonl", help="含最终证明的批量记录")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="runs/strategy-probe.jsonl")
    args = ap.parse_args(argv)

    records = [json.loads(line) for line in Path(args.run).read_text(encoding="utf-8").splitlines()]
    solved = {r["problem_id"]: r for r in records if r.get("status") == "verified"}
    if args.limit:
        records = records[: args.limit]
    problems = {p.problem_id: p for p in load_index()}

    model, note = build_model(allow_network=True)
    print(f"模型={model.name}（{note}）；题数={len(records)}；已解出={len(solved)}", flush=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hits = 0
    scored = 0
    confusion: Counter = Counter()
    with out_path.open("w", encoding="utf-8") as fh:
        for i, rec in enumerate(records, 1):
            pid = rec["problem_id"]
            p = problems.get(pid)
            if p is None:
                continue
            try:
                resp = model.propose(
                    ProposeRequest(problem=p, attempt_index=0, role="strategy_probe")
                )
            except ModelError as exc:
                print(f"  [跳过] {pid}: {exc.kind}", flush=True)
                continue
            pred, conf = roles.parse_probe(resp.text or resp.proof)
            truth = actual_strategy((solved.get(pid, {}).get("proof") or "")) if pid in solved else ""
            row = {
                "problem_id": pid,
                "predicted": pred,
                "confidence": conf,
                "actual": truth,
                "solved": pid in solved,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if truth:
                scored += 1
                if pred == truth:
                    hits += 1
                confusion[(truth, pred)] += 1
            if i % 40 == 0:
                print(f"  … {i}/{len(records)}", flush=True)

    acc = hits / scored if scored else 0.0
    print(f"\n可评估 {scored} 题；top-1 命中 {hits}；准确率 {acc:.1%}")
    print("混淆矩阵（实际 → 预测）:")
    for (truth, pred), n in confusion.most_common(12):
        print(f"  {truth:<14} → {pred:<14} {n}")
    print(f"\n记录：{out_path}")
    if acc < 0.60:
        print("结论：< 60% → 策略标签噪声太大，**跳过 Strategist**（计划 P2 的决策门）。")
    elif acc > 0.80:
        print("结论：> 80% → 模型已隐含掌握，**不加角色，直接做路由**。")
    else:
        print("结论：60–80% → 可以做 Strategist，但只用于路由。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
