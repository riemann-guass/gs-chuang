#!/usr/bin/env python
"""用保存下来的编译器日志**离线重算**一次运行的判定结果。

## 为什么需要这个

判定逻辑（`harness/diagnostics.py` + `harness/verify.py`）本身会演进。当解析器
修掉一个 bug 之后，之前那次运行里被误判的题不应该只能靠「再烧 25 分钟重跑」来纠正。
每次运行的批量文件（`lean/Bench/_work/<run>-r0-cNN.lean`）和原始输出
（`runs/<run>-r0-cNN.lean.log`）都保存着，完全可以离线重算。

## 正确性保证

重算前会**逐字节比对**重新渲染出来的批次文件与原始文件。只要两者一致，
行号区间就完全对应，重算结果与「当时用新代码跑一遍」等价。

**注意**：`harness/leanenv.PREAMBLE` 改动过（例如 `maxHeartbeats` 从 0 改成有界值）之后，
旧批次就再也渲染不出一模一样的文本，脚本会**拒绝重算并退出**。这是故意的——
宁可报错，也不要拿错位的行号去判题。

用法：
    python scripts/reaudit_run.py runs/m1-valid244b.jsonl --chunk-size 60
    python scripts/reaudit_run.py runs/m1-valid244b.jsonl --chunk-size 60 --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import config, leanenv, metrics, runner  # noqa: E402
from harness.problems import Problem, load_index  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="用保存的日志离线重算判定")
    ap.add_argument("run", help="原始 JSONL")
    ap.add_argument("--chunk-size", type=int, default=60)
    ap.add_argument("--write", action="store_true", help="覆盖写回 JSONL（默认只打印差异）")
    args = ap.parse_args()

    run_path = Path(args.run)
    run_id = json.loads(run_path.read_text(encoding="utf-8").splitlines()[0])["run_id"]
    records = metrics.load_jsonl(run_path)
    index = {p.problem_id: p for p in load_index()}

    problems = [index[r["problem_id"]] for r in records]
    states = []
    for r, p in zip(records, problems):
        st = runner.ProblemState(problem=p)
        proof = r["attempts"][0]["proof"]
        st.attempts.append({"round": 0, "source": r["attempts"][0]["source"], "proof": proof})
        st.status = r["status"]  # 让差异输出反映「记录里原本是什么」
        states.append(st)

    size = args.chunk_size
    changes = 0
    for ci in range(0, len(states), size):
        chunk = states[ci : ci + size]
        name = f"{run_id}-r0-c{ci // size:02d}"
        work = config.WORK_DIR / f"{name}.lean"
        log = config.RUNS_DIR / f"{name}.lean.log"
        if not work.is_file() or not log.is_file():
            print(f"[跳过] 缺少 {name} 的批次文件或日志", file=sys.stderr)
            continue

        items = [st.problem.item(st.attempts[-1]["proof"]) for st in chunk]
        batch = leanenv.render_batch(items, config.WORK_DIR / f"{name}.reaudit.lean")
        # 逐字节比对：不一致就说明重算不可信，必须停下
        original = work.read_text(encoding="utf-8").replace("\r\n", "\n")
        if batch.text != original:
            print(f"[中止] {name} 重新渲染的批次与原文件不一致，拒绝重算", file=sys.stderr)
            return 2

        result = leanenv.CompileResult(
            returncode=0,  # 判定不看退出码，见 ADR-0003
            output=log.read_text(encoding="utf-8"),
            # 用记录里原有的批次耗时，避免重算后时间字段归零。
            # 同一块里的题共享同一次编译，所以取该块第一题记录的时间即可。
            duration_ms=int(records[ci]["time_ms"]),
            path=work,
        )
        before = [st.status for st in chunk]
        runner._apply_audits(chunk, batch=batch, result=result, source="cascade")
        for old, st in zip(before, chunk):
            if old != st.status:
                changes += 1
                print(f"  {st.problem.problem_id:<60} {old} -> {st.status} {st.error_types}")

    new_records = [st.to_record(run_id=run_id, model_name="none") for st in states]
    old_sum = metrics.summarize(records)
    new_sum = metrics.summarize(new_records)
    print(f"\n重算前：verified {old_sum.verified}/{old_sum.total}")
    print(f"重算后：verified {new_sum.verified}/{new_sum.total}（{changes} 题状态变化）")

    if args.write:
        runner._write_jsonl(run_path, new_records)
        print(f"已写回 {run_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
