# 文档索引

两份主文档：

- [`AGENT.md`](../AGENT.md)：项目交接文档（**事实来源**，先读这个）
- [`README.md`](../README.md)：快速开始与目录结构

## 决策记录（ADR）

按时间顺序，**后一条可能推翻前一条**，读新结论时注意状态行。

| # | 标题 | 状态 |
|---|---|---|
| [0001](decisions/ADR-0001-lean-environment.md) | Lean / Mathlib 编译环境与版本锁定 | ✅ 已迁移到本仓库 `lean/` |
| [0002](decisions/ADR-0002-model-backend.md) | 模型后端的离线优先设计（Mock/DeepSeek） | ✅ |
| [0003](decisions/ADR-0003-record-schema.md) | 运行记录 JSONL 的 schema 与审计口径 | ✅ |
| [0004](decisions/ADR-0004-batch-chunking.md) | 批量编译必须切块（`maxErrors` 事故） | ✅ |
| [0005](decisions/ADR-0005-deepseek-thinking-mode.md) | DeepSeek 思考模式必须关闭 | ✅ |
| [0006](decisions/ADR-0006-diagnostic-hints.md) | 诊断→对策提示（A/B 证否） | ❌ 默认关闭 |
| [0007](decisions/ADR-0007-persistent-lean-session.md) | 常驻会话：LSP 方案不稳定 | ❌ 已被 0009 取代 |
| [0008](decisions/ADR-0008-single-exe-packaging.md) | 单 exe 分发不可行（没有 Environment） | ❌ 否决 |
| [0009](decisions/ADR-0009-lean-worker.md) | 常驻 worker（`run_tac` + 文件协议） | ✅ 核心 |
| [0010](decisions/ADR-0010-http-service.md) | HTTP 服务 `/health` `/check` `/prove` | ✅ |
| [0011](decisions/ADR-0011-role-architecture.md) | 三角色架构；Critic/Strategist 证否 | ❌ 默认关闭 |
| [0012](decisions/ADR-0012-plan-skeleton-retrieval.md) | 版本化计划有效；骨架/检索默认关 | ✅ 计划保留 |

## 实验记录（按版本）

| 文档 | 内容 | 关键数字 |
|---|---|---|
| [m1-baseline.md](research/m1-baseline.md) | L0 tactic 级联基线（244 题） | 单遍 59 → 两遍 62（25.41%） |
| [m2-result.md](research/m2-result.md) | 接入模型 + 修复回路 | easy +3、medium +16 |
| [m2-smoke.md](research/m2-smoke.md) | Mock 阶段冒烟 | — |
| [m3-hints-ab.md](research/m3-hints-ab.md) | 诊断→对策提示 A/B | 净 +1、token +24% → 无效 |
| [m3-deterministic-remediation.md](research/m3-deterministic-remediation.md) | 确定性补救（放开递归/指数阈值） | 3/7、零 token；全量 +3 |
| [v0.1-evaluation.md](research/v0.1-evaluation.md) | 第一次全流程评测 | 121/244（下界） |
| [v0.5-roles.md](research/v0.5-roles.md) | Critic / 策略预测 A/B | Critic −2（修通道后 +2）；策略 86.4% < 多数类 87.2% |
| [v0.6-plan-skeleton-retrieval.md](research/v0.6-plan-skeleton-retrieval.md) | 版本化计划 / 骨架 / 检索 | **计划 +8/100**；骨架 0 份可用；检索 +1 |

## 调研报告

- [multi-agent-atp-survey.pdf](research/multi-agent-atp-survey.pdf)（LaTeX 源在同目录）
- `abstracts.json` / `abstracts.txt`：文献题录与摘要
- `difficulty.json`：按家族推出的难度分层（easy 60 / medium 124 / hard 60）

## 怎么复现关键数字

```powershell
$py = "C:\Users\gaosen\anaconda3\python.exe"

# 环境与索引
& $py -X utf8 -m harness.cli check

# 244 题全流程（worker 判定 + 批量终审）
& $py -X utf8 -m harness.cli eval-pipeline --select all --split Valid `
    --rounds 2 --remediate --judge worker --network

# 100 题子集：加版本化计划
& $py -X utf8 -m harness.cli eval-pipeline --select all --split Valid --sample 100 `
    --rounds 6 --remediate --judge worker --network --plan

# 汇总任意记录
& $py -X utf8 -m harness.cli report runs\<run>.jsonl --by-family

# worker 回归（用模型写过的证明复判，防判定退化）
& $py -X utf8 scripts\worker_regression.py --run runs\v0.1-valid244.jsonl
```
