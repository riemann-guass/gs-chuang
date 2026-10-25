# ADR-0012：版本化计划有效，骨架与检索默认关闭

- 状态：已采纳（2026-10-24）
- 影响范围：`harness/roles.py`、`harness/retrieval.py`、`harness/pipeline.py`、`harness/worker.py`
- 关联：ADR-0011（单轮 Critic 证否）

## 决策

1. **`--plan` 默认保留为可选能力**，实验证明 +8/100 题；是否默认开启留给后续成本优化。
2. **`--skeleton` 默认关闭**：接口已实现，但 100 题里 0 份可用骨架。
3. **`--retrieval` 默认关闭**：能查到引理（102 条命中），但对通过率只 +1 题。

## 依据

同一 100 题子集、同一判定后端（worker + 批量终审）：

| 组 | pass | token in |
|---|---:|---:|
| 2 轮（v0.5 基线） | 54 | 71k |
| 6 轮（B6） | 52 | 337k |
| 6 轮 + 计划（V1） | **60** | 563k |
| V1 + 骨架 + 检索（V2） | 61 | 588k |

- **计划**：+8 题，增益集中在第 1 轮（30 vs 25），说明它改的是"第一次尝试的质量"。
- **轮数**：6 轮比 2 轮还低 2 题，第 4–6 轮 0 通过 → 单纯的预算扩张无效。
- **骨架**：0 份被记录。样本检查显示模型的"骨架"在 `sorry` 之前就编译失败。
- **检索**：80 次查询、102 条命中，Δ+1（噪声内）。

## 实现要点（给后来人）

- 计划是**落盘、版本化**的：`plan.version / plan_history / outline / lemmas / pitfalls`，
  在 `failed_rounds ∈ {2,4,8}` 重写；`parse_plan` 认不出格式时退化为"整段原文"。
- 骨架的判定是 **`compiles && 0 < sorries ≤ MAX_PROOF_SORRIES`**，只记 `best_skeleton`，
  **绝不改变 `verified`**。
- 检索用 Loogle 公开接口：**必须带 User-Agent**（默认 `Python-urllib` 会被拒），
  失败一律返回空、绝不阻塞主循环。
- 检索触发条件刻意保守：`critic_label == missing_lemma` 或 `failed_rounds ≥ 1`；
  默认关闭时零网络开销。

## 踩到的坑

1. **系统提示与骨架指令冲突**：prover 的系统提示写着"不要使用 sorry"，
   导致骨架功能实际上被禁止。已改成按 `allow_skeleton` 切换两套系统提示，并加回归测试。
2. **`plan` 变量名遮蔽**：`run_pipeline` 里局部变量 `plan` 覆盖了同名参数，
   导致计划阶段根本没进阶段表。已改名 `plan_stages`。
3. **正则吞行**：`OUTLINE\s*:` 里的 `\s*` 会吃掉换行，把第一行大纲吞进 group。
   已统一改成 `[ \t]*`。

## 不做

- 不因为 +8 就把 `--plan` 设成默认开：63% 的 token 增幅对生产环境是显著成本，
  需要先做"只重写一次"的成本优化。
- 不接入 LeanExplore（需要 key）；Loogle 足够验证"检索是否有用"这个命题。
