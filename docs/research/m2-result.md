# M2 结果：cascade + DeepSeek Flash（easy 30 题 / medium 48 题）

- 日期：2026-10-21（easy）、2026-10-22（medium）
- 记录：`runs/m2-easy30b.jsonl`、`runs/m2-medium48.jsonl`（均 gitignored）
- 模型：`deepseek-flash`，`thinking: {type: disabled}`（ADR-0005）
- 环境：Lean `v4.28.0-rc1` + Mathlib `v4.28.0-rc1`，2 轮修复

## 两个档位的结果

| 档位 | 第 0 轮纯级联 | 加模型后 | 净变化 |
|---|---:|---:|---:|
| **easy**（30 题，`mathd_numbertheory`） | 18/30 = 60.0% | 21/30 = **70.0%** | **+3** |
| **medium**（48 题，等距抽样） | 7/48 = 14.6% | 23/48 = **47.9%** | **+16** |

**结论很明确：级联越弱的地方，模型的价值越大。**
easy 档 L0 已经 60%，模型只多拿 3 题；medium 档 L0 只有 14.6%，模型多拿 16 题。

## 关键口径：只看「级联失败」的那部分

整体 pass@1 会被「本来就会的题」稀释，真正要看的是模型在难题上的表现：

| | 值 |
|---|---|
| medium 里级联失败的题 | 41 / 48 |
| 其中模型解出 | **16（39.0%）** |
| 仍未解出 | 25 |

即：**在定式 tactic 全部失败的题上，`deepseek-flash` 两轮内解出 39%。**

## 轮次的边际收益

| 轮次 | 解出题数（medium，共 16 题被补足） |
|---|---:|
| 第 1 轮 | **14** |
| 第 2 轮 | 2 |

**第二轮只多拿 2 题。** 这直接影响后面的预算设计：与其把轮数加到 5–6，
不如把同样的调用花在**换更好的诊断/提示**上。

## 一个必须说清楚的方法学问题

报告里写「模型弄坏 0 题」，但这个 0 **是结构性保证，不是实测结果**：
`run_llm_loop` 只把**未解决**的题送去问模型，已经 verified 的题不会再被提交。
所以「弄坏」在这个回路里**不可能发生**。

这不代表模型不会写坏证明——只代表当前 harness 不给它这个机会。
如果以后做「用模型重写已解出的证明以求更短」，那时才需要真正测回归。

## 成本

| 档位 | 调用次数 | token in / out | 平均每次 |
|---|---:|---|---|
| easy 30 | 22 | 15,343 / 3,277 | 697 / 149 |
| medium 48 | 68 | 46,530 / 14,866 | 684 / 219 |

单次调用 1.3–2 s（关掉思考模式之后）。

## 修掉的两个 harness bug（都在 `extract_proof`）

这两个 bug 直接吃掉了成绩：

1. 模型输出被 `max_tokens` 截断时**围栏没闭合**，去掉 ``` 后残留一行 `lean4`，
   被 Lean 当成 tactic → `unknown tactic`；
2. 同类：没有围栏的裸 `lean4\nsimp`。

easy 档修之前是 **+1**，修之后 **+3**。**有一半的「模型没做出来」是 harness 读错了它的话。**

## 模型在做什么（样例）

**对症下药型** —— `mathd_numbertheory_198`，级联报 `max_rec_depth`，模型第 1 轮：

```lean
set_option maxRecDepth 10000 in
set_option exponentiation.threshold 10000 in
norm_num
```

**搭中间引理型** —— `mathd_numbertheory_257`：

```lean
have h₂ : (∑ k ∈ Finset.range 101, k) = 5050 := by norm_num [Finset.sum_range_id]
rw [h₂] at h₁
have h₃ : x % 77 = 5050 % 77 := by omega
norm_num at h₃
```

**试错型** —— `mathd_numbertheory_232` 第 2 轮才成：`subst` → `rw` → `norm_num [ZMod]` → `decide`。

## 这些数字**不能**说明什么

- **样本小、单次运行、无多种子重跑**：medium +16 在 n=48 上比 easy 的 +3 可信得多，
  但仍是单次测量，不是效应量。
- **只测 `pass@1`**，`pass@k` 未测。
- **medium 是抽样 48 题**（等距抽样，覆盖 4 个家族），不是整个 124 题档位。
- **hard 档完全没测**（L0 在那 60 题上是 0%）。
- 轮数只到 2；第 3 轮的效果未知（第 2 轮只 +2，推测很小）。

## 下一步

1. **「诊断 → 对策」提示的 A/B**：`harness/hints.py` 已就绪（`--hints` 开关），
   针对 `max_rec_depth` / `cascade_exhausted` / `type_mismatch` 给具体建议。
   考虑到第 1 轮就决定 14/16，提示的杠杆点很可能在这里。
2. **hard 档**：L0 = 0%，是模型价值的上限测试，但也要预期成功率很低。
3. 把 medium 扩到整档 124 题，确认 +16 不是抽样侥幸。
