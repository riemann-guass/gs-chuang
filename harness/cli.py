"""命令行入口。

    python -m harness.cli check            # 编译环境自检
    python -m harness.cli eval-cascade     # M1：L0 级联基线
    python -m harness.cli eval-llm         # M2：cascade + 模型修复回路
    python -m harness.cli report <jsonl>   # 汇总一份运行记录
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, leanenv, metrics
from .problems import Problem, family_of, load_index
from .runner import run_cascade, run_llm_loop

#: M1 的 10 题分层抽样规则（家族, 取几题）。
#: 只用 Valid；Test 保留到 M5 之前不碰。
STRATIFIED_10 = (
    ("mathd_algebra_", 4),
    ("induction_", 2),
    ("algebra_", 2),
    ("amc12a_", 1),
    ("imo_", 1),
)


DIFFICULTY_FILE = config.REPO_ROOT / "docs" / "research" / "difficulty.json"


def load_tiers() -> dict[str, list[str]]:
    if not DIFFICULTY_FILE.is_file():
        raise SystemExit(
            f"缺少 {DIFFICULTY_FILE}。先跑一次全量基线，再运行 "
            "`python scripts/difficulty_report.py runs/<run>.jsonl`。"
        )
    return json.loads(DIFFICULTY_FILE.read_text(encoding="utf-8"))["tiers"]


def select_problems(
    problems: list[Problem],
    strategy: str,
    limit: int | None = None,
    split: str = "Valid",
) -> list[Problem]:
    """按 split 过滤后选题。

    `stratified10` 是早期的 10 题冒烟抽样；`all` 取该 split 全部；
    `easy|medium|hard` 按 `docs/research/difficulty.json` 的家族分档筛选。
    """
    if split and split.lower() != "all":
        problems = [p for p in problems if p.split.lower() == split.lower()]

    if strategy in {"easy", "medium", "hard"}:
        fams = set(load_tiers().get(strategy, []))
        picked = sorted(
            (p for p in problems if family_of(p.problem_id) in fams), key=lambda p: p.problem_id
        )
        return picked[:limit] if limit else picked

    if strategy == "all":
        return problems[:limit] if limit else problems

    picked: list[Problem] = []
    for prefix, count in STRATIFIED_10:
        # 按 id 排序保证可复现
        cands = sorted(
            (p for p in problems if p.problem_id.startswith(prefix)),
            key=lambda p: p.problem_id,
        )
        picked.extend(cands[:count])
    if limit:
        picked = picked[:limit]
    return picked


def cmd_check(_args: argparse.Namespace) -> int:
    try:
        leanenv.check_env()
    except leanenv.LeanEnvError as exc:
        print(f"[失败] {exc}", file=sys.stderr)
        return 1
    print(f"[ok] 编译工程：{config.ENV_PROJECT}")
    print(f"[ok] Lean：{config.LEAN_TOOLCHAIN}   Mathlib：{config.MATHLIB_REV}")
    problems = load_index()
    print(f"[ok] bench 索引：{len(problems)} 题")
    return 0


def _apply_slice(problems: list[Problem], spec: str) -> list[Problem]:
    """`--slice start:end`，用于定位「哪一题把 Lean 带崩了」。"""
    if not spec:
        return problems
    start_s, _, end_s = spec.partition(":")
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else len(problems)
    return problems[start:end]


def _apply_sample(problems: list[Problem], n: int) -> list[Problem]:
    """等距抽样，避免 `--limit` 取到的都是同一前缀。

    `medium` 档的 id 是按字母序排的（algebra_* < amc12* < mathd_algebra_*），
    直接 `--limit 40` 会拿到 18 道 algebra + 22 道 amc12a，完全不代表这一档。
    等距抽样能把整个档铺开。
    """
    if not n or n >= len(problems):
        return problems
    step = len(problems) / n
    return [problems[int(i * step)] for i in range(n)]


def cmd_eval_cascade(args: argparse.Namespace) -> int:
    problems = _apply_sample(
        _apply_slice(
            select_problems(load_index(), args.select, args.limit, split=args.split), args.slice
        ),
        args.sample,
    )
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        problems = [p for p in problems if p.problem_id in set(wanted)]
        missing = set(wanted) - {p.problem_id for p in problems}
        if missing:
            print(f"[警告] 这些 id 不在选中集合里：{sorted(missing)}", file=sys.stderr)
    if not problems:
        print("[错误] 没有选中任何题", file=sys.stderr)
        return 2

    opts = list(args.extra_opt or [])
    print(
        f"选题 {len(problems)} 道（split={args.split}, select={args.select}, chunk={args.chunk_size}）"
    )
    if opts:
        print(f"额外 preamble option：{opts}")
    if len(problems) <= 20:
        print("  " + ", ".join(p.problem_id for p in problems))
    print("批量编译（每个 chunk 约 4 分钟，请等待）…", flush=True)
    out, states = run_cascade(
        problems,
        label=args.label,
        allow_test=args.allow_test,
        deep=args.deep,
        chunk_size=args.chunk_size,
        extra_options=opts,
        remediate=args.remediate,
        out_path=Path(args.out) if args.out else None,
    )
    summary = metrics.summarize([s.to_record(run_id="x", model_name="none") for s in states])
    print("\n" + metrics.format_summary(summary, by_family=args.by_family))
    print(f"\n记录：{out}")
    return 0


def cmd_eval_llm(args: argparse.Namespace) -> int:
    from .models import build_model

    problems = _apply_sample(
        _apply_slice(
            select_problems(load_index(), args.select, args.limit, split=args.split), args.slice
        ),
        args.sample,
    )
    model, note = build_model(allow_network=args.network)
    print(
        f"选题 {len(problems)} 道（split={args.split}, chunk={args.chunk_size}）；"
        f"模型 = {model.name}（{note}）；轮数 = {args.rounds}"
    )
    out, states = run_llm_loop(
        problems,
        model,
        rounds=args.rounds,
        label=args.label,
        allow_test=args.allow_test,
        deep=args.deep,
        chunk_size=args.chunk_size,
        use_hints=args.hints,
        out_path=Path(args.out) if args.out else None,
    )
    summary = metrics.summarize([s.to_record(run_id="x", model_name=model.name) for s in states])
    print("\n" + metrics.format_summary(summary, by_family=args.by_family))
    base = metrics.cascade_baseline(metrics.load_jsonl(out))
    print(
        f"\n对照（同一批题、同一次运行）：\n"
        f"  第 0 轮纯级联   {base['verified']}/{base['total']} = {base['pass@1']:.2%}\n"
        f"  最终（含模型）   {summary.verified}/{summary.total} = {summary.pass_at_1:.2%}\n"
        f"  净变化           {summary.verified - base['verified']:+d} 题"
    )
    print(f"\n记录：{out}")
    return 0


def cmd_eval_pipeline(args: argparse.Namespace) -> int:
    """规范路径：按阶段机跑（L0 → 补救 → L1×N）。"""
    from . import pipeline
    from .models import build_model

    problems = _apply_sample(
        _apply_slice(
            select_problems(load_index(), args.select, args.limit, split=args.split), args.slice
        ),
        args.sample,
    )
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        problems = [p for p in problems if p.problem_id in wanted]
    if not problems:
        print("[错误] 没有选中任何题", file=sys.stderr)
        return 2

    model = None
    if args.rounds > 0:
        model, note = build_model(allow_network=args.network)
        print(f"模型 = {model.name}（{note}），轮数 = {args.rounds}")
    print(
        f"选题 {len(problems)} 道（split={args.split}, select={args.select}, "
        f"chunk={args.chunk_size}, remediate={args.remediate}）",
        flush=True,
    )

    out, _states = pipeline.run_pipeline(
        problems,
        model=model,
        rounds=args.rounds,
        remediate=args.remediate,
        chunk_size=args.chunk_size,
        use_hints=args.hints,
        deep=args.deep,
        max_tokens=args.max_tokens,
        max_wall_s=args.max_wall_s,
        judge=args.judge,
        critic=args.critic,
        strategist=args.strategist,
        plan=args.plan,
        retrieval=args.retrieval,
        allow_skeleton=args.skeleton,
        label=args.label,
        allow_test=args.allow_test,
        out_path=Path(args.out) if args.out else None,
    )
    records = metrics.load_jsonl(out)
    summary = metrics.summarize(records)
    print("\n" + metrics.format_summary(summary, by_family=args.by_family))

    base = metrics.cascade_baseline(records)
    print(
        f"\n对照（同一批题、同一次运行）：\n"
        f"  仅 L0          {base['verified']}/{base['total']} = {base['pass@1']:.2%}\n"
        f"  全流程         {summary.verified}/{summary.total} = {summary.pass_at_1:.2%}\n"
        f"  净变化         {summary.verified - base['verified']:+d} 题"
    )
    print(f"\n记录：{out}")
    return 0


def cmd_prove(args: argparse.Namespace) -> int:
    """单题入口（慢：每次都要重载 Mathlib，约 240 s）。"""
    from .prover import Budget, prove

    budget = Budget(
        max_rounds=args.rounds,
        max_tokens=args.max_tokens,
        max_wall_s=args.max_wall_s,
        remediate=not args.no_remediate,
    )
    result = prove(args.statement, budget=budget)
    print(f"状态   {result.status}")
    print(f"阶段   {result.stages}")
    print(f"墙钟   {result.wall_ms / 1000:.1f} s（估计）   token in={result.tokens_in} out={result.tokens_out}")
    cost = "未配置单价" if result.cost_cny is None else f"{result.cost_cny:.4f} 元"
    print(f"成本   {cost}")
    print(f"公理   {result.axioms}")
    if result.proof:
        print("\n证明：")
        print(result.proof)
    return 0 if result.ok else 1


def cmd_worker_check(args: argparse.Namespace) -> int:
    """用常驻 worker 判一道题（不需要批量编译）。"""
    from .cascade import cascade_proof
    from .worker import LeanWorker, binder_count, statement_type

    problems = {p.problem_id: p for p in load_index()}
    if args.problem_id not in problems:
        print(f"[错误] 题号不存在：{args.problem_id}", file=sys.stderr)
        return 2
    p = problems[args.problem_id]
    proof = args.proof or cascade_proof(deep=args.deep)

    print(f"命题：{statement_type(p.header)}")
    print(f"参数：{binder_count(p.header)} 个   证明：{proof[:60]!r}")
    print("启动 worker（首次载入 Mathlib，约 60–240 s）…", flush=True)
    with LeanWorker(request_timeout_s=args.timeout) as w:
        r = w.check_problem(p, proof)
    print(f"\n预热     {w.warmup_s:.1f} s")
    print(f"判定     ok={r.ok}  ({r.reason})")
    print(f"延迟     {r.latency_ms:.0f} ms")
    if r.error:
        print(f"错误     {r.error[:300]}")
    return 0 if r.ok else 1


def cmd_worker_bench(args: argparse.Namespace) -> int:
    """拿一份批量运行记录，用 worker 复判，检查一致性与延迟。

    这是 worker 的回归工具：批量编译是「真相」，worker 必须和它给出同样的判定。
    """
    from .worker import LeanWorker, binder_count, statement_type

    records = metrics.load_jsonl(Path(args.run))
    if not records:
        print(f"[错误] 记录为空：{args.run}", file=sys.stderr)
        return 2
    problems = {p.problem_id: p for p in load_index()}
    if args.limit:
        records = records[: args.limit]

    print(f"记录 {args.run}：{len(records)} 题；启动 worker…", flush=True)
    mismatches: list[tuple[str, bool, bool, str]] = []
    crashes: list[str] = []
    latencies: list[float] = []
    skipped = 0

    worker = LeanWorker(request_timeout_s=args.timeout)
    worker.start()
    print(f"预热完成 {worker.warmup_s:.1f} s\n", flush=True)
    try:
        for i, rec in enumerate(records, 1):
            pid = rec["problem_id"]
            p = problems.get(pid)
            attempts = rec.get("attempts") or []
            if p is None or not attempts:
                skipped += 1
                continue
            proof = attempts[-1].get("proof") or ""
            if not proof:
                skipped += 1
                continue
            want = rec.get("status") == "verified"
            try:
                r = worker.check(statement_type(p.header), proof, nbinders=binder_count(p.header))
            except Exception as exc:  # worker 崩溃：重启后继续（约 60 s）
                crashes.append(pid)
                tail = str(exc).splitlines()[-1][:80] if str(exc) else "?"
                print(f"  [崩溃] {pid}：{tail}；重启 worker…", flush=True)
                worker.stop()
                worker = LeanWorker(request_timeout_s=args.timeout)
                worker.start()
                continue
            latencies.append(r.latency_ms)
            if r.ok != want:
                mismatches.append((pid, r.ok, want, r.reason))
            if args.verbose:
                print(f"  [{i:3d}] {pid:<44} {r.latency_ms:7.1f} ms  ok={r.ok}", flush=True)
            elif i % 20 == 0:
                print(f"  … {i}/{len(records)}", flush=True)
    finally:
        worker.stop()

    n = len(latencies)
    print(f"复判 {n} 题（跳过 {skipped}，崩溃 {len(crashes)}）")
    if n == 0:
        return 1
    latencies.sort()
    print(
        f"延迟   median {latencies[n // 2]:.0f} ms   p90 {latencies[int(n * 0.9) - 1]:.0f} ms"
        f"   max {latencies[-1]:.0f} ms"
    )
    print(f"不一致 {len(mismatches)}/{n}")
    for pid, got, want, reason in mismatches[:15]:
        print(f"  {pid:<40} worker={got} 批量={want}  {reason[:40]}")
    if crashes:
        print(f"崩溃题（worker 侧，需单独排查）：{crashes[:10]}")
    return 0 if not mismatches else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """一条命令起服务：常驻 worker + HTTP 接口。"""
    from .server import serve

    serve(
        host=args.host,
        port=args.port,
        rounds=args.rounds,
        allow_network=args.network,
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    records = metrics.load_jsonl(Path(args.path))
    print(metrics.format_summary(metrics.summarize(records), by_family=args.by_family))
    return 0


def cmd_probe_api(args: argparse.Namespace) -> int:
    """发一次最小请求，验证 API 能力（对应 AGENT.md §11 的未验证项）。"""
    import time

    from .models import MockModel, ModelError, ProposeRequest, build_model

    model, note = build_model(allow_network=True)
    print(f"配置：model={model.name}  note={note}")
    if isinstance(model, MockModel):
        if note == "missing-key-fallback-mock":
            print("[跳过] 缺 DEEPSEEK_API_KEY。")
            print("       复制 .env.example 为 .env，填一行 DEEPSEEK_API_KEY=sk-... 即可")
            print("       （BASE_URL 有默认值 https://api.deepseek.com/v1，通常不用改）。")
        else:
            print(f"[跳过] 未使用真实 API（{note}）。")
        return 2

    probe = Problem(
        problem_id="probe",
        split="Probe",
        header="theorem probe (n : Nat) : n + 0 = n",
        body="",
    )
    started = time.monotonic()
    try:
        resp = model.propose(ProposeRequest(problem=probe, attempt_index=0))
    except ModelError as exc:
        print(f"[失败] kind={exc.kind}\n       {exc.detail[:500]}")
        return 1
    latency_ms = int((time.monotonic() - started) * 1000)

    print(f"[ok] 延迟 {latency_ms} ms")
    print(f"     tokens_in={resp.tokens_in}  tokens_out={resp.tokens_out}")
    print(f"     解析出的 tactic = {resp.proof!r}")
    print(f"     原始输出前 300 字 = {resp.raw[:300]!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="harness", description="miniF2F 证明回路 harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="编译环境与 bench 索引自检").set_defaults(func=cmd_check)

    p1 = sub.add_parser("eval-cascade", help="M1：L0 tactic 级联基线")
    p1.add_argument("--select", default="stratified10", choices=["stratified10", "all", "easy", "medium", "hard"])
    p1.add_argument("--split", default="Valid", choices=["Valid", "Test", "all"], help="默认 Valid；Test 需配合 --allow-test")
    p1.add_argument("--limit", type=int, default=None)
    p1.add_argument("--label", default="m1-cascade")
    p1.add_argument("--allow-test", action="store_true")
    p1.add_argument("--deep", action="store_true", help="把 grind/aesop 也放进级联（更慢，实测 ~2.4x）")
    p1.add_argument("--by-family", action="store_true", help="按题目家族打印 pass@1")
    p1.add_argument("--chunk-size", type=int, default=60, help="每块题数；0 表示全部放进一个文件（危险，见 ADR-0004）")
    p1.add_argument("--slice", default="", help="调试用，形如 100:130，按选中后的顺序切片")
    p1.add_argument("--sample", type=int, default=0, help="等距抽样 N 题，避免 --limit 只取到同一前缀")
    p1.add_argument("--only", default="", help="只跑这些题（逗号分隔 id）")
    p1.add_argument("--extra-opt", action="append", default=[], help="额外 preamble option，如 maxRecDepth=10000，可重复")
    p1.add_argument("--remediate", action="store_true", help="对 max_rec_depth/exponent_threshold 失败题做确定性补救（第二遍，不需要模型）")
    p1.add_argument("--out", default="", help="输出 JSONL 路径（默认 runs/<run_id>.jsonl）")
    p1.set_defaults(func=cmd_eval_cascade)

    p2 = sub.add_parser("eval-llm", help="M2：cascade + 模型修复回路")
    p2.add_argument("--select", default="stratified10", choices=["stratified10", "all", "easy", "medium", "hard"])
    p2.add_argument("--split", default="Valid", choices=["Valid", "Test", "all"], help="默认 Valid；Test 需配合 --allow-test")
    p2.add_argument("--limit", type=int, default=None)
    p2.add_argument("--rounds", type=int, default=6)
    p2.add_argument("--label", default="m2-llm")
    p2.add_argument("--network", action="store_true", help="允许调用真实 API（需要 .env）")
    p2.add_argument("--allow-test", action="store_true")
    p2.add_argument("--deep", action="store_true", help="把 grind/aesop 也放进第 0 轮级联")
    p2.add_argument("--by-family", action="store_true", help="按题目家族打印 pass@1")
    p2.add_argument("--chunk-size", type=int, default=60, help="每块题数；0 表示全部放进一个文件")
    p2.add_argument("--slice", default="", help="调试用，形如 100:130")
    p2.add_argument("--sample", type=int, default=0, help="等距抽样 N 题")
    p2.add_argument("--hints", action="store_true", help="注入「诊断→对策」提示（M3 的 A 组）")
    p2.add_argument("--out", default="", help="输出 JSONL 路径（默认 runs/<run_id>.jsonl）")
    p2.set_defaults(func=cmd_eval_llm)

    p3 = sub.add_parser("report", help="汇总 JSONL")
    p3.add_argument("path")
    p3.add_argument("--by-family", action="store_true")
    p3.set_defaults(func=cmd_report)

    p4 = sub.add_parser("probe-api", help="发一次最小请求验证 DeepSeek API 能力")
    p4.set_defaults(func=cmd_probe_api)

    # 规范路径：阶段机（L0 → 补救 → L1×N）
    p5 = sub.add_parser("eval-pipeline", help="规范路径：按阶段机跑完整流程")
    p5.add_argument("--select", default="all", choices=["stratified10", "all", "easy", "medium", "hard"])
    p5.add_argument("--split", default="Valid", choices=["Valid", "Test", "all"])
    p5.add_argument("--limit", type=int, default=None)
    p5.add_argument("--slice", default="")
    p5.add_argument("--sample", type=int, default=0)
    p5.add_argument("--only", default="")
    p5.add_argument("--rounds", type=int, default=2, help="L1 修复轮数；0 表示只跑 L0(+补救)")
    p5.add_argument("--chunk-size", type=int, default=60)
    p5.add_argument("--remediate", action="store_true", help="启用确定性补救阶段")
    p5.add_argument("--hints", action="store_true", help="（已证否）注入诊断提示")
    p5.add_argument("--deep", action="store_true")
    p5.add_argument("--network", action="store_true", help="允许调用真实 API")
    p5.add_argument("--max-tokens", type=int, default=20_000, help="单题 token 预算")
    p5.add_argument("--max-wall-s", type=float, default=0.0, help="整批墙钟预算（秒，0=不限）")
    p5.add_argument("--judge", default="batch", choices=["batch", "worker"], help="L1 判定后端：batch=批量编译（真相源），worker=常驻进程加速 + 最后终审")
    p5.add_argument("--critic", action="store_true", help="启用 Critic 角色（失败闭集分类）")
    p5.add_argument("--strategist", action="store_true", help="启用 Strategist 角色（门控：策略类失败或连续失败≥3）")
    p5.add_argument("--plan", action="store_true", help="启用版本化证明计划（第 0 轮生成，2/4/8 轮重写）")
    p5.add_argument("--retrieval", action="store_true", help="在缺失引理/第二次失败后查 Loogle")
    p5.add_argument("--skeleton", action="store_true", help="允许返回带 sorry 的可编译骨架（不算通过）")
    p5.add_argument("--allow-test", action="store_true")
    p5.add_argument("--by-family", action="store_true")
    p5.add_argument("--label", default="pipeline")
    p5.add_argument("--out", default="")
    p5.set_defaults(func=cmd_eval_pipeline)

    p6 = sub.add_parser("prove", help="单题证明（慢，每次约 240 s 载入 Mathlib）")
    p6.add_argument("statement", help='Lean 定理语句，如 "theorem foo (n : Nat) : n + 0 = n"')
    p6.add_argument("--rounds", type=int, default=2)
    p6.add_argument("--max-tokens", type=int, default=20_000)
    p6.add_argument("--max-wall-s", type=float, default=0.0)
    p6.add_argument("--no-remediate", action="store_true")
    p6.set_defaults(func=cmd_prove)

    # 常驻 worker：一次导入 Mathlib，之后每题 0.05–3 s
    p7 = sub.add_parser("worker-check", help="用常驻 worker 判一道题（不做批量编译）")
    p7.add_argument("problem_id")
    p7.add_argument("--proof", default="", help="覆盖默认的 L0 级联证明")
    p7.add_argument("--deep", action="store_true")
    p7.add_argument("--timeout", type=float, default=120.0, help="单题超时（秒）")
    p7.set_defaults(func=cmd_worker_check)

    p8 = sub.add_parser("worker-bench", help="用 worker 复判一份批量记录，检查一致性")
    p8.add_argument("run", help="批量运行记录 JSONL")
    p8.add_argument("--limit", type=int, default=0)
    p8.add_argument("--timeout", type=float, default=120.0)
    p8.add_argument("--verbose", action="store_true", help="逐题打印，便于定位崩溃点")
    p8.set_defaults(func=cmd_worker_bench)

    p9 = sub.add_parser("serve", help="起 HTTP 服务（常驻 worker + /check + /prove）")
    p9.add_argument("--host", default="127.0.0.1")
    p9.add_argument("--port", type=int, default=8080)
    p9.add_argument("--rounds", type=int, default=0, help="模型修复轮数；0 = 只试 L0 级联")
    p9.add_argument("--network", action="store_true", help="允许调用真实 API（rounds>0 时）")
    p9.set_defaults(func=cmd_serve)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
