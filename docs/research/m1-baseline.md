# M1 基线：L0 tactic 级联（244 题 / miniF2F Valid）

> **更新（2026-10-22）**：加上「确定性补救」第二遍之后，正式基线是
> **62/244 = 25.41%**（`runs/m1-two-pass.jsonl`）。下面 59/244 是**单遍**基线，
> 保留作为对照。两遍的做法与差别见 `docs/research/m3-deterministic-remediation.md`。

- 日期：2026-10-20（首版 2026-10-19 为 10 题冒烟）
- 运行记录：`runs/m1-valid244b.jsonl`（gitignored）
- 环境：Lean `v4.28.0-rc1` + Mathlib `v4.28.0-rc1`（ADR-0001）
- 模型：无（纯 tactic 级联，`model = none`，token = 0）
- 级联版本：`L0-v1`（记录里 `ladder_version` 字段）

## 结果

| 项 | 值 |
|---|---|
| 题数 | 244（Valid 全集） |
| **verified** | **59（pass@1 = 24.18%）** |
| 失败 | 185 |
| 失败类型 | `cascade_exhausted` 178，`max_rec_depth` 7 |
| 公理 | 全部 verified 题的 `#print axioms` ⊆ `{propext, Classical.choice, Quot.sound}`，无 `sorryAx` |

### 按家族

| 家族 | 题数 | 通过 | pass@1 | 档位 |
|---|---:|---:|---:|---|
| mathd_numbertheory | 60 | 35 | 58.3% | easy |
| mathd_algebra | 70 | 17 | 24.3% | medium |
| algebra | 18 | 4 | 22.2% | medium |
| amc12 | 5 | 1 | 20.0% | medium |
| amc12a | 31 | 2 | 6.5% | medium |
| aime / aimeI / aimeII | 15 | 0 | 0% | hard |
| amc12b | 9 | 0 | 0% | hard |
| imo | 20 | 0 | 0% | hard |
| induction | 8 | 0 | 0% | hard |
| numbertheory | 8 | 0 | 0% | hard |

**解读**：L0 基本只会做「化简型」题（`mathd_*` 里的算术/代数恒等式），
凡是需要归纳、构造、多步推理的（`induction_*`、`imo_*`、`aime_*`）**一题都没做出来**。
这正好说明为什么必须有 L1（模型 + Lean 反馈）——级联的天花板就在这里。

## 7 个 `max_rec_depth` 是什么

`max_rec_depth` = Lean 的递归深度上限（默认 1000）被撞到，典型场景是
在大指数/大整数上跑 `simp`/`decide`。这**不是**我们的 bug，是 tactic 本身的限制；
但如果 L1 之后要处理这类题，可能需要调 `set_option maxRecDepth` 或改写策略。

## 本次踩到的两个坑（都是自己的代码）

### 1. 244 题塞进一个文件 → 后 133 题根本没跑

第一次跑（`runs/m1-valid244.jsonl`）得到 **9/244**。真实原因是：整个文件一次编译，
**只有前 110 题有诊断输出**，后面 133 题一条消息都没有，却被记成 `failed`——
看起来像「证明失败」，其实是根本没被 Lean 处理。

当时的缓存放大了问题：没有保存原始编译器输出，无法判断是崩了、卡了还是被杀。
现在已做三件事（ADR-0004）：

- `--chunk-size`（默认 60）切块编译，限制爆炸半径；
- 每块保留 `runs/<name>.lean.log`；
- 既无诊断又无公理报告的题，标 `status=error` + `error_types=["batch_truncated"]`，
  **不再冒充 `failed`**。

切块后重跑得到 59/244，说明之前那个 9/244 完全是统计事故。

### 2. 定理名太长时 `#print axioms` 会折行 → 解析器认不出

`algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta` 的名字超长，
Lean 输出时按 80 列折成三行：

```
'M0019.algebra_3rootspoly_amdtamc...' depends on axioms: [propext,
 Classical.choice,
 Quot.sound]]
```

解析器原先要求整条在一行，于是这题拿不到公理报告 → 被误判成 `batch_truncated`。
修好后它是 **verified**，总数从 58 变 59。

为了不因为「解析器修好了」就重跑 25 分钟，加了 `scripts/reaudit_run.py`：
用保存下来的批次文件 + 原始日志**离线重算**判定，且重算前逐字节比对批次文件，
保证行号区间对应。

## 成本

| 项 | 值 |
|---|---|
| 块数 | 5（244 / 60） |
| 每块耗时 | 约 240–290 s（Mathlib 载入为主） |
| 总墙钟 | 约 20 分钟 |
| 成本模型 | 块数 × 240 s + 244 × ~1 s |

单块 60 题比单块 244 题慢在「载入 5 次」，换来的是统计不再可能被静默污染。

## 局限

- **10 题冒烟版（4/10）已作废**：那 10 题是按字母序取的前几个 `mathd_algebra_*`，
  恰好偏简单，40% 是抽样偏差，不代表 244 题水平。
- `time_ms` 在批量模式下是**共享上界**，且本次记录经过离线重算后已归零；
  批次耗时以运行日志为准（ADR-0003）。
- 分层（`docs/research/difficulty.json`）是**从 L0 自己的结果**推出来的，
  只能用于给后续实验挑子集，**不能**用来评价 L0（循环论证）。

## 下一步

M2 的真实 API 对照：`easy` 档 60 题是理想的起点（L0 已有 58.3%，
能看清模型是「补足剩余 42%」还是「把已会的搞坏」）。
