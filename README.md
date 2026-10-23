# 大创2 / sgs-change-two

面向 Lean 形式化数学与自动定理证明（ATP）的研究仓库。

目标：输入一个 Lean 4 定理语句，输出一个能被 Lean kernel 验证的证明；先在 miniF2F 上跑通闭环，
最终做成可用的软件 App。详见 [`AGENT.md`](AGENT.md)。

## 目录结构

```text
.
├── AGENT.md            # 项目交接文档（事实来源）
├── arxiv论文/           # ATP / Lean 文献库：PDF、分类清单与检索元数据
├── harness/            # 证明回路：批量编译、诊断解析、四项审计、模型后端、指标
├── lean/               # Lean 侧文件与 miniF2F bench（生成物，见 lean/README.md）
├── scripts/            # 薄入口（gen_bench 等）
├── tests/              # pytest，全部离线可跑
├── docs/
│   ├── research/       # 多 Agent ATP 调研报告（PDF + LaTeX 源）
│   └── decisions/      # ADR-0001..0003
├── runs/               # 运行记录 JSONL（gitignored）
└── data/               # 本地缓存（gitignored）
```

## 当前状态（2026-10-23）

- **引擎 v0.1 成型**：`harness/prover.py` 是对外接口（`prove` / `prove_many`），
  `harness/pipeline.py` 是阶段机（L0 → 确定性补救 → L1×N），可扩 L2/L3。
- **常驻 worker 跑通**：`lean/Worker.lean` 一次导入 Mathlib（60–65 s），
  之后每题 **median 168 ms**；241 题复判 **0 不一致**（ADR-0009）。
- **成绩**：L0 两遍 **62/244 = 25.41%**；全流程加模型 **121/244 = 49.59%**。
- 79 个离线单测全绿。详见 [`AGENT.md`](AGENT.md) 与 `docs/research/`。

## 快速开始

```powershell
# Python 用 anaconda 的绝对路径（PATH 上没有 python）
$py = "C:\Users\gaosen\anaconda3\python.exe"

& $py -X utf8 scripts\gen_bench.py            # 生成 lean/Bench（需 miniF2F 上游 checkout）
& $py -X utf8 -m harness.cli check            # 环境自检
& $py -X utf8 -m pytest tests -q              # 离线单测（约 3 秒）

# 单题（批量路径：每次都要重载 Mathlib，约 4 分钟）
& $py -X utf8 -m harness.cli prove "theorem foo (n : Nat) : n + 0 = n"

# 单题（常驻 worker：预热一次 60 s，之后 0.2 s/题）
& $py -X utf8 -m harness.cli worker-check mathd_numbertheory_198

# 起 HTTP 服务（/health /check /prove）
& $py -X utf8 -m harness.cli serve --port 8080

# 批量评测（规范路径）
& $py -X utf8 -m harness.cli eval-pipeline --select easy --rounds 2 --remediate --network
```

**注意**：worker 会像真正的声明一样先引入定理参数，所以证明里**不要再写 `intro`**。

```powershell
# 对
theorem t (n : Nat) : n + 0 = n := by rfl
# 错（会报 no additional binders）
theorem t (n : Nat) : n + 0 = n := by intro n; rfl
```

库用法：

```python
from harness.prover import Budget, prove_many
from harness.problems import load_index

results = prove_many(load_index()[:10], budget=Budget(max_rounds=2))
print(sum(r.ok for r in results), "/", len(results))
```

编译环境依赖本地 `D:\bianma\code\大创\sgs-reap\sgslean` 的完整 Mathlib，
原因与迁移计划见 [`ADR-0001`](docs/decisions/ADR-0001-lean-environment.md)。

## 文献使用说明

`arxiv论文/` 中的 PDF 仅用于研究阅读与引用。正式引用时请以论文的原始出版信息为准。
