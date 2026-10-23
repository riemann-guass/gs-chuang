# ADR-0006：「诊断 → 对策」提示（M3 的 A 组）

- 状态：**已实现，A/B 未通过，保持默认关闭**（2026-10-22）
- 影响范围：`harness/hints.py`、`harness/models.py`（`--hints`）

## 背景

M2 里最有信息量的一条证据：`mathd_numbertheory_198` 的第 0 轮级联报的是
`max_rec_depth`（Lean 递归深度上限），模型第 1 轮直接给出：

```lean
set_option maxRecDepth 10000 in
set_option exponentiation.threshold 10000 in
norm_num
```

它**读懂了诊断，并且知道对应的开关**。而同一批里还有 6 道 `max_rec_depth` 的题
模型没救回来——说明它并不是稳定地掌握这个映射。

调研报告 §5.2 原计划是「结构化 goal state」，但那要改协议、改解析、再重跑对照；
相比之下，「诊断类型 → 具体对策」只是一张表加一段 prompt，成本低一个数量级。

## 决策

新增 `harness/hints.py`：

```python
COUNTERMEASURES = {
  "max_rec_depth": ("set_option maxRecDepth 10000 in ...", "exponentiation.threshold ..."),
  "cascade_exhausted": ("simp_all / nlinarith / split ...",),
  "type_mismatch": ("norm_cast / push_cast ...",),
  ...
}
```

- 输入是**已有的** `error_kind` 分类（`harness/diagnostics.classify()`），不需要新解析。
- 注入位置在 prompt 末尾，标题明确写「建议…不保证正确」，避免模型盲从。
- **默认关闭**，只有 `--hints` 才注入。原因：历史运行（`m2-easy30b`、`m2-medium48`）
  都是无提示的，改默认会让新旧记录不可比。

## 已知局限

1. 这张表是**手写的先验**，不是从数据里学出来的；每条的准确率未知。
2. 提示依赖 `error_kind` 分类的质量。当前分类是正则匹配，`other` 占比不低。
3. 提示可能让模型**无视真正的 goal state** 而机械套用建议——尤其 `cascade_exhausted`
   那条给了 5 个候选 tactic，可能诱导它乱试。

## 验证方式

同一批题（`--select medium --sample 24`）、同一环境、1 轮，跑两臂：

```
eval-llm --select medium --sample 24 --rounds 1 --network --label m3-hints-off
eval-llm --select medium --sample 24 --rounds 1 --network --hints --label m3-hints-on
```

比较「级联失败题中被解出的比例」。n=24 只够看方向，不做显著性断言。

## 如果 A/B 显示无效

不要硬推。可能的下一步：
- 只对 `max_rec_depth` / `exponent_threshold` 这类**确定性映射**开提示
  （它们有明确正确的答案），其余类型不给；
- 或者干脆把这两类做成 **L0 的确定性补救**：级联失败后，用提高限制的选项重跑一次
  同一批 tactic——完全不需要模型。

## A/B 结果（2026-10-22，结论：无效）

24 题、1 轮、两臂对照（详见 `docs/research/m3-hints-ab.md`）：

| | 加模型后 | 净变化 |
|---|---:|---:|
| A 无提示 | 12/24 = 50.0% | +8 |
| B 有提示 | 13/24 = 54.2% | +9 |

配对差异：**新增 2 题、丢失 1 题，净 +1**；输入 token 多花 **24%**。

结论：

- **`--hints` 保持默认关闭**，不并入主流程；
- 多付 24% token 换 +1 题（n=24）不成立；而且它**丢掉了一道原本能做的题**，
  说明提示会干扰模型原有判断；
- 按上面「如果 A/B 显示无效」的第二条走：把 `max_rec_depth` / `exponent_threshold`
  这两类做成**确定性补救**，绕开 prompt。

**负结果同样是结果**：它说明在「模型已经能解 50%」的设定里，prompt 微调的效应
很容易被单题方差淹没；要提升应优先找**确定性收益**。

## 后续：确定性补救已落地并验证（2026-10-22）

按上面第二条走：把 `max_rec_depth` / `exponent_threshold` 做成**不需要模型**的补救。
对 M1 里 7 道 `max_rec_depth` 的题，用同一套 L0 tactic 在提高限制的 preamble 下重跑：

```lean
set_option maxHeartbeats 200000      -- 必须！否则 simp/norm_num 会跑飞（实测 >20 min）
set_option maxRecDepth 10000
set_option exponentiation.threshold 10000
```

**结果 3/7 救回**，零 token。其中 2 题（236、690）是模型在 M2 里没解出的
——确定性补救与模型**互补**。详见 `docs/research/m3-deterministic-remediation.md`。

实现：`--extra-opt`（可重复）+ `--only`（逗号分隔 id），见 `harness/cli.py`。
