# M3 替代路线：确定性补救（不需要模型）

- 日期：2026-10-22
- 记录：`runs/remediate-bounded.jsonl`
- 触发背景：M2 里模型靠 `set_option maxRecDepth 10000 in` 救回一题，
  而提示语的 A/B 又无效（`docs/research/m3-hints-ab.md`）。那就**把这条知识写死**，
  不让模型参与。

## 做法

M1 的 244 题基线里有 7 道题以 `max_rec_depth` 失败（Lean 的递归深度上限）。
对**这 7 道题**，用**同一套 L0 tactic**重跑一次，只改 preamble：

```lean
set_option maxHeartbeats 200000        -- 必须有界，见下
set_option maxRecDepth 10000
set_option exponentiation.threshold 10000
```

`--extra-opt` 开关已加进 CLI：

```powershell
python -m harness.cli eval-cascade --select all --split Valid --only <7 个 id> \
  --extra-opt maxHeartbeats=200000 \
  --extra-opt maxRecDepth=10000 \
  --extra-opt exponentiation.threshold=10000
```

## 结果：3 / 7 救回，**零模型调用**

| 题目 | 结果 | 备注 |
|---|---|---|
| `mathd_numbertheory_198` | ✅ verified | 模型在 M2 里也解出过这题 |
| `mathd_numbertheory_236` | ✅ verified | **模型没解出** |
| `mathd_numbertheory_690` | ✅ verified | **模型没解出** |
| `mathd_numbertheory_109` | ❌ 心跳超时 | 预算内没算完，见下 |
| `mathd_numbertheory_43` | ❌ `cascade_exhausted` | 真的要换 tactic，不是限制问题 |
| `amc12a_2003_p1` | ❌ 仍是 `max_rec_depth` | 10000 还不够 |
| `mathd_numbertheory_543` | ❌ 仍是 `max_rec_depth` | 同上 |

**3/7 = 42.9%，代价是 0 token、一次编译（约 28 分钟，主要花在 Mathlib 载入和两题的长搜索上）。**

对比：同样这 7 题，M2 里模型只解出 1 题（198）。而且 236、690 是模型没做到的——
说明**确定性补救和模型是互补的**，不是替代关系。

## 接进 L0 之后：244 题整体 +3（零 token）

`--remediate` 开关已接进 `eval-cascade`。在 **244 题 Valid** 上跑两遍：

```powershell
python -m harness.cli eval-cascade --select all --split Valid --chunk-size 60 --remediate
```

| | verified | pass@1 |
|---|---:|---:|
| 单遍 L0（`m1-valid244b`） | 59/244 | 24.18% |
| **两遍 L0（`m1-two-pass`）** | **62/244** | **25.41%** |
| 变化 | **+3** | **+1.23 个百分点** |

- 补救**只触发在 7 道题**上（`attempts` 分布 `{1: 237, 2: 7}`），没有波及其它题；
- 新增的正是 `mathd_numbertheory_198 / 236 / 690`，**丢失 0 题**；
- `mathd_numbertheory` 家族 35/60 → **38/60（58.3% → 63.3%）**；
- 代价：**0 token**，多一轮编译（补救批次约 28 分钟，主要被两题的长时间搜索占据）。

这与上面的独立实验（3/7）**完全一致**，说明整条链路（触发条件 → 分批 → 审计 → 记录）
能稳定复现。

## 一个必须记住的坑：不加心跳上限会跑飞

第一次跑时只加了 `maxRecDepth` 和 `exponentiation.threshold`，心跳仍是无限：

- 7 道题跑满 **20 分钟**仍未结束（lean 进程 3.2 GB、持续占 CPU）；
- 原因是提高递归深度之后 `simp`/`norm_num` 不再「快速失败」，而是真的往里搜。

加上 `maxHeartbeats 200000`（Lean 的默认值）后，同一批题 **28 分钟**内出结果。
其中 109 被这个上限截断（报 `maximum number of heartbeats (200000) has been reached`），
但那至少是一个**确定的结论**，而不是无限等待。

**结论：提高限制类 option 必须配心跳上限一起用。**

## 对 L0 的设计含义

这不该是一次性实验，而应该是级联的一个**条件分支**：

```text
L0 跑完
  ├─ 解出 → 结束
  └─ 失败且诊断 ∈ {max_rec_depth, exponent_threshold}
        → 用「提高限制」的 preamble 对这批题再跑一遍（成本：一次批量编译）
```

代价很小：只有少数题会进入这个分支，而且不需要模型、可以离线复现。

## 局限

- 只测了 7 道题，样本极小；3/7 的置信区间很宽。
- `maxRecDepth 10000` 是拍的，没有扫参；243 号题的失败说明 10000 不一定够。
- 心跳上限 200000 会误杀慢证明（109 就是这样），这个值需要根据预算调。
- 这 7 题是从 **M1 的 244 题**里找出来的，属于「事后选样」。要做成方法，
  应该在全量上跑一遍「L0 → 补救」两段流程，报整体增量。
