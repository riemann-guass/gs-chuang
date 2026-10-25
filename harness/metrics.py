"""从 JSONL 运行记录里算指标。

口径（与调研报告 §3.4 一致）：

* `pass@1` = `status == "verified"` 的题目比例，**不区分**尝试次数；
* 同时给出 `attempts` 分布，便于反推 pass@k；
* 时间与 token 都按「参与的批次之和」统计，批量模式下是上界。
"""

from __future__ import annotations

import json
import statistics
from collections import Counter

from . import config
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Summary:
    total: int = 0
    verified: int = 0
    failed: int = 0
    error: int = 0
    timeout: int = 0
    error_kinds: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)
    attempts_hist: Counter = field(default_factory=Counter)
    time_ms: list[int] = field(default_factory=list)
    wall_ms: list[int] = field(default_factory=list)
    stage_solved: Counter = field(default_factory=Counter)
    critic_labels: Counter = field(default_factory=Counter)
    worker_crash: int = 0
    plans: int = 0
    skeletons: int = 0
    retrieval_queries: int = 0
    retrieval_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    fam_total: Counter = field(default_factory=Counter)
    fam_verified: Counter = field(default_factory=Counter)

    @property
    def pass_at_1(self) -> float:
        return (self.verified / self.total) if self.total else 0.0

    def by_family(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for fam, n in self.fam_total.items():
            v = self.fam_verified.get(fam, 0)
            out[fam] = {"total": n, "verified": v, "pass@1": round(v / n, 4) if n else 0.0}
        return dict(sorted(out.items(), key=lambda kv: (-kv[1]["pass@1"], kv[0])))

    def by_stage(self) -> dict[str, int]:
        """哪一阶段解出了题（按 attempts 的最后来源统计）。"""
        return dict(sorted(self.stage_solved.items(), key=lambda kv: -kv[1]))

    def as_dict(self) -> dict:
        wall = [int(r) for r in self.wall_ms if r]
        cost = config.token_cost_cny(self.tokens_in, self.tokens_out)
        return {
            "total": self.total,
            "verified": self.verified,
            "failed": self.failed,
            "pass@1": round(self.pass_at_1, 4),
            "error_kinds": dict(self.error_kinds),
            "fail_reasons": dict(self.reasons),
            "attempts_hist": dict(sorted(self.attempts_hist.items())),
            "time_ms_total": sum(self.time_ms),
            "time_ms_median": int(statistics.median(self.time_ms)) if self.time_ms else 0,
            "wall_ms_median": int(statistics.median(wall)) if wall else 0,
            "wall_ms_p90": int(sorted(wall)[int(len(wall) * 0.9) - 1]) if wall else 0,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_cny": round(cost, 4) if cost is not None else None,
            "by_family": self.by_family(),
            "by_stage": self.by_stage(),
            "critic_labels": dict(self.critic_labels),
            "worker_crash": self.worker_crash,
            "plans": self.plans,
            "skeletons": self.skeletons,
            "retrieval": {"queries": self.retrieval_queries, "hits": self.retrieval_hits},
        }


def summarize(records: list[dict]) -> Summary:
    from .problems import family_of

    s = Summary()
    for r in records:
        s.total += 1
        fam = r.get("family") or family_of(r.get("problem_id", ""))
        s.fam_total[fam] += 1
        status = r.get("status", "error")
        if status == "verified":
            s.verified += 1
            s.fam_verified[fam] += 1
            attempts = r.get("attempts") or []
            src = attempts[-1].get("source", "?") if attempts else "?"
            s.stage_solved[src] += 1
        elif status == "timeout":
            s.timeout += 1
        elif status == "error":
            s.error += 1
        else:
            s.failed += 1

        for k in r.get("error_types", []) or []:
            s.error_kinds[k] += 1
        if "worker_crash" in (r.get("error_types") or []):
            s.worker_crash += 1
        critic = r.get("critic") or {}
        label = critic.get("label") or ""
        if label:
            s.critic_labels[label] += 1
        plan = r.get("plan") or {}
        if int(plan.get("version", 0) or 0) > 0:
            s.plans += 1
        if r.get("best_skeleton"):
            s.skeletons += 1
        ret = r.get("retrieval") or {}
        s.retrieval_queries += int(ret.get("queries", 0) or 0)
        s.retrieval_hits += int(ret.get("hits", 0) or 0)
        for a in r.get("attempts", []):
            kind = a.get("error_kind")
            if kind and kind != "none":
                s.reasons[kind] += 1

        s.attempts_hist[len(r.get("attempts", []))] += 1
        s.time_ms.append(int(r.get("time_ms", 0)))
        s.wall_ms.append(int(r.get("wall_ms", 0) or 0))
        s.tokens_in += int(r.get("tokens_in", 0))
        s.tokens_out += int(r.get("tokens_out", 0))
    return s


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cascade_baseline(records: list[dict]) -> dict:
    """从**同一次** LLM 运行里取出「第 0 轮级联」的成绩。

    这样对照的两边共享完全相同的环境（同一个 Lean 版本、同一份 preamble、
    同一个批次切分），比拿另一次历史运行来比要可靠——历史运行的设置可能已经变了。
    """
    total = len(records)
    solved = 0
    for r in records:
        attempts = r.get("attempts") or []
        if attempts and attempts[0].get("status") == "verified":
            solved += 1
    return {
        "total": total,
        "verified": solved,
        "pass@1": round(solved / total, 4) if total else 0.0,
    }


def format_summary(summary: Summary, *, by_family: bool = False) -> str:
    d = summary.as_dict()
    cost = d["cost_cny"]
    lines = [
        f"题数        {d['total']}",
        f"verified    {d['verified']}  (pass@1 = {d['pass@1']:.2%})",
        f"failed      {d['failed']}",
        f"尝试次数分布 {d['attempts_hist']}",
        f"失败类型     {d['error_kinds']}",
        f"按阶段解出   {d['by_stage']}",
    ]
    if d["critic_labels"]:
        lines.append(f"Critic 标签  {d['critic_labels']}")
    if d["plans"]:
        lines.append(f"计划 / 骨架  {d['plans']} 份 / {d['skeletons']} 题")
    if d["retrieval"]["queries"]:
        lines.append(f"检索         {d['retrieval']['queries']} 次 query，命中 {d['retrieval']['hits']} 条")
    if d["worker_crash"]:
        lines.append(f"worker 崩溃  {d['worker_crash']} 题（已从模型失败中单列）")
    lines += [
        f"单题墙钟     median {d['wall_ms_median'] / 1000:.0f} s  p90 {d['wall_ms_p90'] / 1000:.0f} s（估计值）",
        f"总编译耗时   {d['time_ms_total'] / 1000:.1f} s（批量模式为共享上界）",
        f"token       in={d['tokens_in']} out={d['tokens_out']}",
        f"成本        {'未配置单价（.env 里填 DEEPSEEK_PRICE_*）' if cost is None else f'{cost:.4f} 元'}",
    ]
    if by_family and d["by_family"]:
        lines.append("")
        lines.append(f"{'家族':<20}{'题数':>5}{'通过':>6}{'pass@1':>9}")
        for fam, row in d["by_family"].items():
            lines.append(f"{fam:<20}{row['total']:>5}{row['verified']:>6}{row['pass@1']:>9.1%}")
    return "\n".join(lines)
