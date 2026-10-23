# ADR-0007：常驻 Lean 会话（LSP）—— 协议通了，但不稳定，暂不接入

- 状态：**已被 ADR-0009 取代**（2026-10-23）。LSP 这条路放弃，改用
  `run_tac` + 文件协议的常驻 worker，已跑通并在 241 题上验证 0 不一致
- 影响范围：`harness/lsp.py`（保留作参考，未接线）

## 动机

每次批量编译都要重新 `import Mathlib`（约 240 s）。如果有一个常驻 Lean 进程，
Mathlib 只载入一次，之后每个文件只做增量检查——这是 App 能交互的前提，也是
多轮 / 多角色 Agent 的成本基础。

`lean --server` 就是 Lean 自带的 LSP 服务，`harness/lsp.py` 实现了最小客户端。

## 已经确认能工作的部分

1. **LSP 握手**：`initialize` → `initialized` → `didOpen`，约 7 s（不含 Mathlib）。
2. **server→client 请求**必须回复，否则会卡（`client/registerCapability`、
   `workspace/inlayHint/refresh` 等），已处理。
3. **诊断确实能拿到**。一次成功观测（`import Mathlib` + 一个类型错误）：

```
 0.0s  fileProgress processing=[1]
 0.3s  publishDiagnostics []          ← 先清空，空的
39.6s  fileProgress processing=[4..1]  ← 载入 Mathlib
39.6s  publishDiagnostics [1 条]      ← 真正的诊断
39.7s  fileProgress processing=[]     ← 处理完成
```

**这条序列本身是重要发现**：`didOpen` 之后立刻到的 `publishDiagnostics` 是空的，
必须等 `$/lean/fileProgress` 的 `processing` 归零才能取结果。早期版本只等第一条
publish，于是永远读到「0 条诊断」，看起来像「LSP 没工作」。

## 为什么不接进去

**同一个文件、同样内容，隔一段时间再跑，420 秒都没等到 `processing` 归零。**

- 第一次：39.6 s 完成；
- 第二次（新进程、已清理残留 lean）：超时 420 s，期间 `fileProgress`、
  `publishDiagnostics` 都在发，但 `processing` 始终不空。

也就是说**完成信号不可靠**，而整个 API 的正确性依赖它。在这种情况下把它接进
`prove()` 会让结果变得不可重复——这比慢更糟。

可能的解释（都未证实）：
- LSP 的 worker 进程会为每个文件重新载入 imports，长文件更慢；
- 机器内存/IO 压力下 Mathlib 载入时间波动极大（60 s – 400 s+）；
- 我们的客户端缺少某些 capability，导致 server 走了退化路径。

## 净收益（这次尝试里真正落地的部分）

虽然 LSP 没接进去，但为了让 LSP 有工程可用，复制出了**本仓库自己的 Lake 工程**：

- `lean/` 现在是完整 Lake 包（`lakefile.toml` + `lake-manifest.json` + 6 GB 的
  `.lake/packages`，从已有构建 `robocopy` 而来）；
- `lake build` = 7890 jobs，**只重编译 `Bench`**，Mathlib 全部复用；
- `harness.config.ENV_PROJECT` 已从外部仓库切到 `lean/`；
- 单文件编译从 ~240 s 降到 **~67 s**。

这一步消除的是**跨仓库依赖**（原来整个 harness 依赖 `大创/sgs-reap/sgslean` 存在），
这比 LSP 更基础。

## 下一步（v0.2 再做）

1. 先量清楚：**服务端到底在等什么**。用 `DSH_LSP_DEBUG=1` 打开现有的消息追踪，
   对比成功与失败两次的 `fileProgress` 内容差异。
2. 试 `capabilities` 补齐（`workspace.configuration`、`experimental` 等），
   看是否改变 server 的路径。
3. 如果仍然不稳定，就绕过 LSP：**自建常驻 worker**——一个 Lean 进程用
   `--stdin` 或自定义脚本循环读文件路径并输出 `--json` 消息。这条路不依赖 LSP 语义。
4. 判断标准：**连续 10 个文件，每个 < 15 s，且诊断与批处理一致**，才算可用。
