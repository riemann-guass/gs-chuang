# 大创2 / sgs-change-two

面向 Lean 4 形式化数学与自动定理证明（ATP）的研究仓库。

目标：输入一个 Lean 4 定理语句，输出一个能被 Lean kernel 验证的证明；先在 miniF2F 上跑通闭环，
最终做成可用的软件 App。详见 [`AGENT.md`](AGENT.md)（事实来源）与 [`docs/README.md`](docs/README.md)（文档索引）。

## 目录结构

```text
.
├── AGENT.md            # 项目交接文档（事实来源，先读这个）
├── arxiv论文/           # ATP / Lean 文献库（120 篇 PDF）
├── harness/            # 引擎：编译 / 诊断 / 审计 / 阶段机 / 模型 / worker / HTTP
├── lean/               # 自包含 Lake 工程（含 Mathlib oleans），见 lean/README.md
├── scripts/            # 离线工具（建 bench、兼容性扫描、对比、回归、探针）
├── tests/              # pytest，全部离线可跑
├── docs/
│   ├── README.md       # 文档索引（ADR + 实验记录）
│   ├── decisions/      # ADR-0001 … ADR-0012
│   └── research/       # 调研报告（PDF+LaTeX）与各版本实验记录
├── runs/               # 运行记录 JSONL + 编译日志（gitignored）
└── data/               # 本地缓存（Loogle 检索缓存等，gitignored）
```

`harness/` 分层：

| 层 | 模块 | 职责 |
|---|---|---|
| 编译 | `leanenv` `diagnostics` `verify` `cascade` | 批量渲染/编译、解析输出、四项审计、L0 阶梯 |
| 编排 | `pipeline` `runner` `prover` | 阶段机、编译原语、对外接口 |
| 模型 | `models` `roles` `retrieval` `hints` | DeepSeek/Mock 客户端、角色 prompt、Loogle 检索 |
| 加速 | `worker` | 常驻 Lean 会话（一次导入，之后 0.2 s/题） |
| 服务 | `server` `cli` | HTTP 接口与命令行 |
| 未接线 | `goals` | 目标状态解析（保留，暂未接入） |

## 当前状态（2026-10-25）

- **引擎**：`prover`（库接口）+ `pipeline`（L0 → 确定性补救 → 计划 → L1×N）+ `worker`（快验证）+ `serve`（HTTP）。
- **成绩**：L0 两遍 **62/244 = 25.41%**；全流程加模型 **125/244 = 51.23%**；
  100 题子集上，6 轮 + 版本化计划 **60/100**（比同预算不加计划 +8，ADR-0012）。
- **常驻 worker**：一次导入 60–65 s（冷缓存可达 577 s），之后每题 median **168 ms**；
  241 题复判 **0 不一致**（ADR-0009）。
- **148 个离线单测全绿**。

## 快速开始

```powershell
# Python 用 anaconda 的绝对路径（PATH 上没有 python）
$py = "C:\Users\gaosen\anaconda3\python.exe"

& $py -X utf8 scripts\gen_bench.py            # 生成 lean/Bench（需 miniF2F 上游 checkout）
& $py -X utf8 -m harness.cli check            # 环境自检
& $py -X utf8 -m pytest tests -q              # 离线单测（约 4 秒）

# 单题：常驻 worker（预热一次 60 s，之后 0.2 s/题）
& $py -X utf8 -m harness.cli worker-check mathd_numbertheory_198

# 批量评测（worker 判定 + 批量终审）；--plan 是当前唯一验证有效的增强
& $py -X utf8 -m harness.cli eval-pipeline --select all --split Valid --rounds 6 `
    --remediate --judge worker --network --plan

# 起 HTTP 服务（/health /check /prove）
& $py -X utf8 -m harness.cli serve --port 8080
```

**注意**：worker 会像真正的声明一样先引入定理参数，所以证明里**不要再写 `intro`**。

```lean
-- 对
theorem t (n : Nat) : n + 0 = n := by rfl
-- 错（会报 no additional binders）
theorem t (n : Nat) : n + 0 = n := by intro n; rfl
```

库用法：

```python
from harness.prover import Budget, prove_many
from harness.problems import load_index

results = prove_many(load_index()[:10], budget=Budget(max_rounds=2))
print(sum(r.ok for r in results), "/", len(results))
```

编译环境是**本仓库自己的** `lean/`（完整 Lake 工程，Mathlib `v4.28.0-rc1`），
不再依赖外部 checkout；换机器需要重新准备 `.lake/packages`，见
[`ADR-0001`](docs/decisions/ADR-0001-lean-environment.md) 与 [`lean/README.md`](lean/README.md)。

## 文献使用说明

`arxiv论文/` 中的 PDF 仅用于研究阅读与引用。正式引用时请以论文的原始出版信息为准。
