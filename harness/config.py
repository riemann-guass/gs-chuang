"""全局路径与运行环境配置。

本项目的 Lean 编译环境在 P0 阶段**借用**另一个本地工程
（`D:\\bianma\\code\\大创\\sgs-reap\\sgslean`，Lean v4.28.0-rc1），
因为：

1. 本机当前无网络，无法 `lake exe cache get` 或重新 clone Mathlib；
2. 本地唯一**完整**的 Mathlib 构建就在那个工程里（7527 个 olean，
   含根模块 `Mathlib.olean`）。`mathematics_in_lean` 下那份 v4.21.0
   只有 2687 个 olean、缺根模块，`import Mathlib` 会失败。

迁移手段见 `docs/decisions/ADR-0001`。

所有路径都允许用环境变量覆盖，便于以后把编译环境搬进本仓库。
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- 版本口径
LEAN_TOOLCHAIN = "leanprover/lean4:v4.28.0-rc1"
MATHLIB_REV = "v4.28.0-rc1"

#: L0 tactic 级联的「代次」。改 `harness/cascade.py` 的阶梯时必须同步改这里，
#: 否则新旧运行记录会混在一起、无法判断差异来自代码还是来自题目。
LADDER_VERSION = "L0-v1"

# ---------------------------------------------------------------- 编译环境
# 承载完整 Mathlib 的 Lake 工程；harness 用 `lake env lean` 在其中编译。
# 2026-10-22：已经迁到本仓库自己的 `lean/`（ADR-0001 的迁移计划已执行），
# 不再依赖 `D:\bianma\code\大创\sgs-reap\sgslean`。
ENV_PROJECT = Path(
    os.environ.get(
        "MINIF2F_ENV_PROJECT",
        str(REPO_ROOT / "lean"),
    )
)

# ---------------------------------------------------------------- 目录
LEAN_ROOT = REPO_ROOT / "lean"
BENCH_DIR = LEAN_ROOT / "Bench"
WORK_DIR = BENCH_DIR / "_work"
INDEX_FILE = BENCH_DIR / "index.jsonl"

DATA_DIR = REPO_ROOT / "data"
# miniF2F 上游 checkout（只读来源，生成时复制/派生，不改动它）
RAW_MINI2F = Path(
    os.environ.get(
        "MINIF2F_RAW",
        r"D:\bianma\code\大创\sgs-reap\data\raw\miniF2F-lean4",
    )
)

RUNS_DIR = REPO_ROOT / "runs"

# ---------------------------------------------------------------- 编译参数
# 单次批量编译的墙钟上限（秒）。实测 `import Mathlib` 单次约 240 s，
# 批量文件与题目数几乎无关，所以上限要留得足够宽。
COMPILE_TIMEOUT_S = int(os.environ.get("MINIF2F_COMPILE_TIMEOUT", "1800"))

#: 单个声明的心跳上限。**单位是「千次心跳」**（Lean 的约定），
#: 200000 意味着 2 亿 tick，不是 20 万。别按字面调小。
#: miniF2F 原文件写的是 `maxHeartbeats 0`（无上限），这里默认保持 0 以忠于上游语义；
#: 真正的硬兜底是下面的墙钟超时（`leanenv.compile_file` 会捕获并标成 `batch_timeout`）。
MAX_HEARTBEATS = int(os.environ.get("MINIF2F_MAX_HEARTBEATS", "0"))

# 允许出现在公理审计里的公理（Mathlib 经典默认集）。
ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# 证明文本中禁止出现的 token（按词边界匹配）。
FORBIDDEN_TOKENS = ("sorry", "admit", "native_decide", "axiom", "unsafe")

# ---------------------------------------------------------------- 确定性补救
#: 当 L0 因 `max_rec_depth` / `exponent_threshold` 失败时，用同一套 tactic
#: 在下面这些额外 option 下重跑一遍（不需要模型）。
#:
#: **`maxHeartbeats` 必须在内且必须有界**：实测只提高 `maxRecDepth` 而不设心跳上限，
#: 7 道题跑满 20 分钟都结束不了——`simp`/`norm_num` 不再快速失败，而是真的往里搜。
REMEDY_OPTIONS: tuple[str, ...] = (
    "maxHeartbeats=200000",
    "maxRecDepth=10000",
    "exponentiation.threshold=10000",
)

#: 触发补救的诊断类型（见 `harness/diagnostics.classify()`）。
REMEDY_TRIGGERS = frozenset({"max_rec_depth", "exponent_threshold"})

#: 补救轮自己的墙钟上限（秒）。
#: 实测 7 题在 `maxRecDepth 10000` 下要跑约 1700 s（提高限制后 simp 真的往里搜），
#: 所以这里给到 2400 s；设小了会把整批判成 batch_timeout，白白丢掉已经解出的题。
REMEDY_TIMEOUT_S = int(os.environ.get("MINIF2F_REMEDY_TIMEOUT", "2400"))

#: L1（模型）批次的心跳上限，单位同样是「千次心跳」。
#: 默认 0 = 不加限制（与历史 m2-* 运行一致）。设成 200000 可以防止单条模型证明
#: 拖住整块——实测一个 60 题 L1 批次跑满 30 分钟，正好贴着 `COMPILE_TIMEOUT_S`。
L1_MAX_HEARTBEATS = int(os.environ.get("MINIF2F_L1_MAX_HEARTBEATS", "0"))

#: 终审（worker 放行后的一次批量复核）的参数。
#: 小块 + 硬超时 + 超时保留判定：模型证明里常有极慢的 tactic，一整块 60 题撞上
#: 1800 s 会波及 60 道已经通过的题（2026-10-24 实测把 60 题从 verified 打成 error）。
AUDIT_CHUNK_SIZE = int(os.environ.get("MINIF2F_AUDIT_CHUNK", "40"))
AUDIT_TIMEOUT_S = int(os.environ.get("MINIF2F_AUDIT_TIMEOUT", "600"))

#: 单次 worker 判定的超时（秒）。
#: 太短会把「慢但有效」的证明判成崩溃并触发重启（一次重启 ≈ 4–5 分钟预热），
#: 实测 120 s 会导致每 15 分钟重启一次；300 s 更划算。
WORKER_CHECK_TIMEOUT_S = float(os.environ.get("MINIF2F_WORKER_TIMEOUT", "300"))

# ---------------------------------------------------------------- 计划 / 检索
#: 计划在哪些尝试次数上重写（对齐 Numina-Lean-Agent 的 2^n 检查点）。
#: 第 0 轮必定生成 v1；之后命中这些次数时带着失败历史重写。
PLAN_CHECKPOINTS: tuple[int, ...] = (2, 4, 8)

#: Loogle 的公开 JSON 接口（无需 key）。实测 `?q=Nat.add_comm` 返回 200。
LOOGLE_URL = os.environ.get("MINIF2F_LOOGLE_URL", "https://loogle.lean-lang.org/json")
RETRIEVAL_TIMEOUT_S = float(os.environ.get("MINIF2F_RETRIEVAL_TIMEOUT", "8"))
#: 单轮最多发几条 query，避免把检索变成新的延迟来源。
RETRIEVAL_MAX_QUERIES = int(os.environ.get("MINIF2F_RETRIEVAL_QUERIES", "2"))
#: 单次检索最多注入几个候选引理。
RETRIEVAL_MAX_HITS = int(os.environ.get("MINIF2F_RETRIEVAL_HITS", "5"))
RETRIEVAL_CACHE = DATA_DIR / "loogle_cache.jsonl"

#: 骨架里允许出现的 `sorry` 个数上限（超过视为无效，不记为进展）。
MAX_PROOF_SORRIES = int(os.environ.get("MINIF2F_MAX_SORRIES", "1"))


# ---------------------------------------------------------------- 计量
def _float_env(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


#: 每百万 token 的人民币单价。**默认 None = 未配置**，此时成本一律报 `None`，
#: 绝不用编造的价格算出一个看起来像真的数字。请在 `.env` 里按你的实际账单填。
PRICE_IN_CNY_PER_MTOK = _float_env("DEEPSEEK_PRICE_IN_CNY_PER_MTOK")
PRICE_OUT_CNY_PER_MTOK = _float_env("DEEPSEEK_PRICE_OUT_CNY_PER_MTOK")


def token_cost_cny(tokens_in: int, tokens_out: int) -> float | None:
    """按配置的单价算人民币成本；未配置单价时返回 None。"""
    if PRICE_IN_CNY_PER_MTOK is None or PRICE_OUT_CNY_PER_MTOK is None:
        return None
    return (tokens_in / 1e6) * PRICE_IN_CNY_PER_MTOK + (tokens_out / 1e6) * PRICE_OUT_CNY_PER_MTOK


def ensure_dirs() -> None:
    for d in (WORK_DIR, RUNS_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
