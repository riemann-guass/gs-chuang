"""worker 回归测试：用**模型写过的证明**复判，防止判定逻辑退化。

## 为什么需要它

`worker-bench` 只复判记录里的**最终证明**，而 L0 级联的证明不引用定理参数名。
2026-10-24 就因此漏掉一个真实 bug：worker 把参数统一改名成 `arg`，
导致所有引用 `a` / `h₀` 的模型证明都报 `Unknown identifier`——
244 题回归 0 不一致，但模型解出的题从 59 掉到 2。

所以这个脚本只挑**非 cascade 来源**的通过证明来复判。

用法：
    python scripts/worker_regression.py --run runs/v0.1-valid244.jsonl --min 0.95
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.problems import load_index  # noqa: E402
from harness.worker import LeanWorker  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/v0.1-valid244.jsonl")
    ap.add_argument("--min", type=float, default=0.95, help="最低通过率，低于它退出码 1")
    ap.add_argument("--show", type=int, default=6, help="打印前几个失败样例")
    args = ap.parse_args(argv)

    rows = [
        json.loads(x)
        for x in Path(args.run).read_text(encoding="utf-8").splitlines()
    ]
    solved = [
        r
        for r in rows
        if r.get("status") == "verified"
        and (r.get("attempts") or [{}])[-1].get("source") not in (None, "cascade", "cascade-remedy")
    ]
    if not solved:
        print(f"{args.run} 里没有「模型解出」的题，跳过")
        return 0

    problems = {p.problem_id: p for p in load_index()}
    ok = bad = 0
    failures: list[tuple[str, str, str]] = []
    with LeanWorker(request_timeout_s=180) as w:
        print(f"预热 {w.warmup_s:.1f}s；复判 {len(solved)} 个模型证明", flush=True)
        for r in solved:
            p = problems.get(r["problem_id"])
            if p is None:
                continue
            res = w.check_problem(p, (r["attempts"] or [{}])[-1].get("proof") or "")
            if res.ok:
                ok += 1
            else:
                bad += 1
                failures.append((r["problem_id"], res.reason, res.error[:120]))

    rate = ok / (ok + bad) if (ok + bad) else 0.0
    print(f"\n通过 {ok}/{ok + bad} = {rate:.1%}（门槛 {args.min:.0%}）")
    for pid, reason, err in failures[: args.show]:
        print(f"  ✗ {pid:<34} {reason:<14} {err}")
    if rate < args.min:
        print("回归失败：worker 判定与批量编译不一致，先查 mkGoal / 判定逻辑。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
