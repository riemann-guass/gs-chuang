# ADR-0011：角色架构 —— 3 个 LLM 角色封顶，黑板 + 确定性编排

- 状态：**设计已实现，A/B 证否（Critic/Strategist 默认关闭）**，2026-10-24
- 影响范围：`harness/roles.py`、`harness/pipeline.py`、`harness/models.py`、`harness/runner.py`

## 决策

1. **最多 3 个 LLM 角色**：Prover（写）、Critic（判）、Strategist（全局策略）。
   第 4 个角色默认不做——除非它能落进「局部/全局 × 产出/判断」里空着的那格。
2. **写者唯一**：只有 Prover 的产物会进入 Lean。Critic 只输出闭集标签，Strategist 只输出
   策略文本，二者永不直接编译。
3. **黑板而非对话**：角色之间不互相发消息，只读写 `ProblemState` 上的字段
   （`critic_label` / `critic_note` / `strategy` / `failed_rounds`）。
4. **Strategist 必须门控**：只有 `critic_label ∈ {wrong_strategy, needs_induction}`
   或 `failed_rounds ≥ 3` 时才调用；否则等于给 L1 加一倍成本。
5. **先测后训**：不训练策略分类器。先用 `scripts/strategy_probe.py` 量出 Flash 的策略预测
   准确率，< 60% 就跳过 Strategist。

## 判据：什么时候才值得拆一个新 agent

三条至少满足一条，否则只是「同一模型换个 prompt」：

| 判据 | 含义 |
|---|---|
| 上下文必须隔离 | 它读的东西会污染主循环（长日志、检索结果） |
| 判定权必须独立 | 它不能自己判自己对（验证、分类） |
| 能力/工具集不同 | 不同模型、不同工具，且并行有收益 |

## 实现

* `harness/roles.py`：闭集、prompt、解析器（纯字符串，可离线单测）。
  - Critic 标签闭集：`syntax` / `missing_lemma` / `wrong_strategy` / `needs_induction` /
    `type_mismatch` / `unsolved` / `other`。
  - 解析失败一律落回 `other`，且置信度记 0，不假装有信号。
* `models.ProposeRequest.role`：`prover`（默认）/ `critic` / `strategist` / `strategy_probe`。
  `system_prompt(role)` 分派；未知角色退回 prover，避免静默丢角色。
* `pipeline.pipeline_v1(rounds, remediate, critic, strategist)`：每轮交错展开
  `L1 → [Critic] → [Strategist]`，让 Critic 看到的是**本轮**失败的诊断。
* `Stage.predicate`：`triggers` 只能按 `error_types` 匹配，表达不了「轮数 + 标签」的组合门控。

## 记录格式

加法字段（`schema` 仍为 1，消费者向后兼容）：

```json
{"critic": {"label": "wrong_strategy", "note": "…"}, "strategy": "…", "failed_rounds": 2}
```

`error_types` 里可能出现 `worker_crash`（worker 静默崩溃），指标里**单列**，
不并入「模型没证出」。

## A/B 结果（2026-10-24）

三次运行都同一配置：244 Valid / `--rounds 2 --remediate --judge worker`，
Critic 与基线在**同一个 100 题等距子集**上比较（244 全量跑三轮太慢，子集是确定性的）。

| 运行 | 子集 pass@1 | Δ | token in | token out | 墙钟 | 结论 |
|---|---|---|---|---|---|---|
| **P0 基线（无角色）** | **54/100 = 54.0%** | — | 71,149 | 40,292 | 1000 s | — |
| **P1 +Critic** | **52/100 = 52.0%** | **−2** | 120,351 (+69%) | 45,662 (+13%) | 1140 s | ❌ 不保留 |

（全量 244 的 P0 基线：**125/244 = 51.23%**，L0 59 + 模型 66。）

**决策 G1：把 Critic 关掉。** 准确率 −2 题、输入 token +69%、墙钟 +14%，
三个方向全错。这与讨论里的预测 #4 一致（"加 Critic 的 Δ ≈ 0 → 纯开销"）。

Critic 的标签分布也说明了原因：两轮里 `unsolved` 占 39/77 与 34/54，
它基本只会说"你没证完"，而这正是 Prover 早就知道的信息；
真正有路由价值的 `wrong_strategy`（2）和 `needs_induction`（1）几乎不出现。

## 策略探针（P2-pre）：模型没有策略信号

按计划在实现 Strategist 之前先量了一次（244 题、每题一次调用）：

| 指标 | 值 |
|---|---|
| 可评估题（已解出、能用最终证明打弱标签） | 125 |
| 模型 top-1 命中 | 108 = **86.4%** |
| **全猜多数类（direct）的命中率** | **87.2%** |
| 相对多数类的增益 | **−0.8%** |

**模型比"永远猜 direct"还差 0.8 个点。** 标签分布极度偏斜（direct 109/125），
所以 86.4% 这个数字本身没有意义——它低于平凡基线。

**决策：跳过 Strategist（P2）。** 不是"效果不确定"，而是"连做它的前提都不成立"：
模型无法区分策略，路由就没有可路由的信号。

（脚本里的自动结论说 ">80% → 做路由"，那是被类别不平衡骗了；
**任何准确率都必须和多数类基线比**，这条要写进后续所有探针。）

## 事故记录（2026-10-24，做基线时踩到的三个坑）

这三件事都不是"角色设计"的问题，而是**测量基础设施**的问题，但每一个都足以让 A/B 结论反转：

1. **worker 把定理参数改名成 `arg`** → 所有引用 `a` / `h₀` 的模型证明都报
   `Unknown identifier`，基线从 121 掉到 61。而 `worker-bench`（只复判级联证明）
   完全发现不了，因为级联证明不引用参数名。
   **修**：`withLocalDecl name bi …` 保留原始 binder 名。
   **加**：`scripts/worker_regression.py`——只复判**模型写过的**证明。
2. **终审超时把已验证的题降级** → 一块 60 题的终审撞上 1800 s，60 道已通过的题
   被打成 `error`，基线从 ~121 掉到 58。
   **修**：`keep_on_timeout`——超时只记 `audit_timeout`，保留 worker 的判定；
   终审改成小块（40）+ 硬超时（600 s）。
3. **`lake env lean` 被 kill 时留下孤儿 `lean`**（吃 3+ GB）→ 重启后两个 lean 抢 CPU，
   单次判定从 0.2 s 退化到几十秒。
   **修**：`stop()` 用 `taskkill /T /F` 杀进程树。

**教训**：在比较"加了角色有没有用"之前，先确认"测量工具本身没有坏"。
这三条都应该固化成回归测试，而不是留在人的记忆里。
