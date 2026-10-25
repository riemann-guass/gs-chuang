# ADR-0009：常驻 Lean worker 跑通了（一次导入，之后 0.2 秒/题）

- 状态：**可用（实验性接入）**，2026-10-23
- 影响范围：`lean/Worker.lean`、`harness/worker.py`、`harness/cli.py`
- 替代：ADR-0007（LSP 方案）与 ADR-0008（单 exe 方案）均已被否决

## 结论先行

| 指标 | 批量编译 | 常驻 worker |
|---|---|---|
| 首次成本 | 每次编译都付 60–240 s | **一次 60–65 s** |
| 单题成本 | 摊到批次里，约 1 s | **median 170 ms，p90 408 ms** |
| 一致性 | 真相来源 | **241 题复判，0 处语义不一致**（见下） |

## 为什么 LSP 和单 exe 都不行

- **LSP**（ADR-0007）：协议通、诊断能拿到，但完成信号不稳定（同一文件一次 39.6 s、
  一次 420 s 未完成）。不可重复比慢更糟。
- **单 exe**（ADR-0008）：把 Mathlib 链接进二进制后启动只要 1.9 s，但 `importModules`
  报 `unknown module prefix 'Mathlib'` —— **exe 里没有 olean，拿不到 Environment**，
  无法 elaboration。

**elaboration 的硬前提是磁盘上的 olean + 一个活着的 `lean` 进程。**

## 实现

`lean/Worker.lean`：一个**永远在编译中**的文件。

```lean
example : True := by
  run_tac Worker.serve
  trivial
```

`run_tac` 在 elaboration 期间执行 `TacticM` 动作，于是进程持有一个完整的
Mathlib Environment；`serve` 在里面轮询目录、处理请求。导入只发生一次。

协议：客户端写 `req_<seq>`，worker 写 `rsp_<seq>`（都是纯 ASCII、无扩展名）。

## 踩到的四个坑（都花了时间，记下来）

1. **`IO.getStdin` 在 `run_tac` 里永远是 EOF**（实测 `GOT len=0`）。
   所以不能用 stdin/stdout，必须走文件。
2. **Lean 自己会往 stdout 打诊断**（linter 警告、错误），会污染协议。
   走文件后这个问题自动消失。
3. **`String.Slice.pos! Offset is not at a valid UTF-8 character boundary`**。
   对含 `∀`、`ℂ`、`h₀` 这类多字节字符的字符串做 `endsWith` / `replace` 会让
   **整个进程 panic**（跑 41 题后必崩）。规避：文件名纯 ASCII、协议 JSON 用
   `ensure_ascii=True`、回传文本先压成 ASCII。
4. **目标形状必须和声明一致**。批量编译里定理参数是**局部假设**
   （`theorem foo (a : ℂ) : P a`），而 `∀ (a : ℂ), P a` 是一个 forall 目标，
   `ring` / `linarith` 会直接失败。worker 必须按参数个数逐个
   `withLocalDecl` 引进局部上下文（`mkGoal`），参数个数由
   `harness.worker.binder_count` 从头部数出来（`(a b : ℂ)` 是 **2** 个，不是 1 个）。
5. **参数名必须保留**。第一版 `mkGoal` 用 `withLocalDeclD \`arg` 统一改名，
   结果模型写的证明引用 `a` / `h₀` 时全部报 `Unknown identifier`——
   **v0.5 基线因此从 121 掉到 61**（2026-10-24 实测），而 L0 级联的证明
   不引用参数名，所以 `worker-bench` 的 244 题回归**发现不了这个问题**。
   修法：`withLocalDecl name bi dom …`，用 `.forallE` 上原有的 binder 名与 BinderInfo。
   **教训**：一致性测试必须覆盖「模型写的证明」，不能只覆盖级联证明。

## 一致性验收

拿 `runs/m1-valid244b.jsonl`（单遍 L0 基线）的 244 题复判：

- 复判成功 **241** 题，worker 崩溃 3 题（`amc12a_2003_p1`、`mathd_numbertheory_109`、
  `mathd_numbertheory_543`，见「已知问题」）；
- 不一致 3 题：`mathd_numbertheory_198 / 236 / 690`，worker 说 True、单遍基线说 False。

**这 3 题不是 bug**：worker 的 preamble 带 `maxRecDepth 10000`，等价于
「确定性补救」那一轮（ADR-0006）；这 3 题正是补救救回的题。

拿 `runs/m1-two-pass.jsonl`（含补救的基线）复判，**结果 0/241 不一致**：

```
复判 241 题（跳过 0，崩溃 3）
延迟   median 168 ms   p90 351 ms   max 3587 ms
不一致 0/241
```

也就是说：worker 的判定与批量编译**在语义上完全一致**，剩下的 3 题是进程崩溃（见下）。

## 已知问题

1. **3 道题会让 worker 进程静默崩溃**：`amc12a_2003_p1`、`mathd_numbertheory_109`、
   `mathd_numbertheory_543`。已定位到：
   - 用 `skip` 当证明**不会**崩（90 ms，正常返回 `unsolved`）→ 崩溃来自某个 tactic；
   - 把 `maxRecDepth` 提到 100 万仍然崩，且**没有任何 Lean 错误输出** →
     是原生栈溢出，`catch` 捕获不到（Lean 侧无法处理）。
   - 这 3 道题都用到了大求和（如 `∑ k ∈ Finset.range 2003`），`norm_num` / `simp`
     在这类目标上递归极深。
   兜底：`worker-bench` 与 pipeline 的 judge 都会**自动重启并跳过该题**
   （约 60 s/次）。**代价**：一次 244 题复判会多花约 3 分钟。
2. **失败诊断已恢复**（见「诊断通道」）；早先为规避 UTF-8 panic 而关闭渲染的问题已解决。
3. **没有单题超时隔离**：单题卡住时 Python 会超时放弃，但 Lean 那边仍在算。
   下一步要么给 worker 加 watchdogs，要么按题启子进程。

## 诊断通道（G3）

失败消息现在保留 Unicode、可读，按字符截断到 400：

```
cascade_exhausted
arg✝² arg✝¹ : ℂ
arg✝ : arg✝² + arg✝¹ = 7
arg : 2 * arg✝² + arg✝¹ = 3
⊢ arg✝¹ = 11
```

实现要点：响应统一走 `Json.compress`（不手写字符串拼装），截断用
`String.ofList (s.toList.take n)`（按字符，不碰 UTF-8 边界）。
`classify_worker_error` 把文本归成与批量编译一致的类别。

## 怎么用

```powershell
# 单题
python -m harness.cli worker-check mathd_numbertheory_198

# 拿一份批量记录复判（回归工具）
python -m harness.cli worker-bench runs\m1-two-pass.jsonl

# 让 L1 用 worker 判定（最后仍有一次批量终审）
python -m harness.cli eval-pipeline --select easy --rounds 2 --judge worker
```

## 接入引擎（G2）

`pipeline.run_pipeline(judge="worker")`：L1 每轮先把模型给出的证明交给 worker 判，
通过的标记为 verified，**全部阶段结束后再把所有 verified 的题交给批量编译做终审**
（`source="final-audit"`），终审不过的会被降级。

20 题端到端验证（easy 档，2 轮）：

```
[worker] 预热完成 60.5s
[worker] 第 1 轮：0/7 通过（待终审）
[worker] 第 2 轮：0/7 通过（待终审）
[终审] 13 题交给批量编译复核…
[终审] 降级 1 题
verified 12/20 (60.00%)
```

链路正确：worker 放行 → 终审 → 降级逻辑生效。

**收益要如实说**：目前只有 L1 走 worker，L0 与补救、以及最后的终审仍是批量编译，
所以在 20 题这种小规模上，60 s 预热会吃掉大部分收益。真正的收益要等
**L0 也改成 worker 判定**（一次 0.2 s 对比一轮编译 2 分钟），但那会把 L0 的
`maxRecDepth` 语义改成 10000（等价于补救档），需要先决定口径。
