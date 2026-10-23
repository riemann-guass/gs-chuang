# ADR-0003：运行记录 schema 与「证明成功」判定

- 状态：已采纳（2026-10-19）
- 影响范围：`harness/runner.py`、`harness/verify.py`、`harness/metrics.py`

## 背景

调研报告 §3.4 的结论：文献里的 `pass@k`、采样预算、时间口径差异可达几个数量级，
**跨系统比较必须先对齐口径**。项目自己如果不把口径写死，连自己的历史版本都不可比。

同时，Lean 侧有一个容易踩的坑：**批量编译时进程退出码不能作为单题成败的判据**。
只要文件里有一道题失败，`lake env lean` 就返回 1，但同文件里其它题可能都证完了。

## 决策一：判定规则

一道题记为 `verified`，当且仅当同时满足：

1. 该题 span 内**没有** `error` 级诊断；
2. `#print axioms` 里**没有** `sorryAx`；
3. 公理集合 ⊆ `{propext, Classical.choice, Quot.sound}`；
4. 证明文本里没有 `sorry` / `admit` / `native_decide` / `axiom` / `unsafe`（按词边界）。

第 2 条同时覆盖两种情况：显式写了 `sorry`，以及 elaboration 失败被 Lean 用
`sorryAx` 补洞。实测确认，失败的定理仍会出现在环境里并报告 `sorryAx`，
所以这一条是可靠的失败信号。

第 3 条是 Mathlib 的经典默认公理集。`sorryAx` 之外，任何额外公理都判失败。

## 决策二：记录 schema（每题一行 JSONL）

```json
{
  "schema": 1,
  "run_id": "m1-cascade-20261019-231500",
  "problem_id": "mathd_algebra_10",
  "split": "Valid",
  "status": "verified | failed | timeout | error",
  "proof": "norm_num",
  "attempts": [
    {"round": 0, "source": "cascade", "proof": "first | ...", "status": "verified",
     "error_kind": "none", "diagnostics": "...", "compile_ms": 236900, "compile_shared": true}
  ],
  "time_ms": 236900,
  "time_shared": true,
  "compile_rounds": 1,
  "tokens_in": 0,
  "tokens_out": 0,
  "model": "none",
  "lean_toolchain": "leanprover/lean4:v4.28.0-rc1",
  "mathlib_rev": "v4.28.0-rc1",
  "axioms": ["propext", "Classical.choice", "Quot.sound"],
  "error_types": [],
  "statement_sha256": "sha256:...",
  "timestamp": "2026-10-19T15:15:00+00:00"
}
```

约定：

- **`pass@1` 不单独存**，由 `status == "verified"` 的比例算出；`attempts` 长度即尝试次数，
  所以任意 `pass@k` 都可以事后推导。
- **`time_ms` 是「参与的批次耗时之和」，且 `time_shared: true`**。批量编译的耗时无法
  分摊到单题，这个数是上界而非单题真实耗时。要真实单题时间，用 `--no-batch`。
- `model` 为 `none` 表示该轮没有调用模型（纯 cascade）。
- 任何一次运行都必须带 `lean_toolchain` 与 `mathlib_rev`，否则不可复现。

## 决策三：Test 集守卫

`runner._guard_split()`：只要题目里有 `split == "Test"`，且没有显式 `--allow-test`，
直接 `SystemExit`。目的是防止在最终测试集上调参——这是文献里最常见的隐形泄漏。

## 后果

- 好处：口径写在记录里，不需要靠记忆；批量编译的成本被诚实标注为上界。
- 代价：`time_ms` 在批量模式下不能直接和文献里的单题耗时比较，报告时必须说明。
- 已知未做：公理审计目前只覆盖 `#print axioms` 的主定理，不递归检查它引用的辅助声明。
  如果以后 LLM 能自己新增 `lemma`，需要扩展为对整个文件做公理审计。
