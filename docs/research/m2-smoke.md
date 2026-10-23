# M2 冒烟记录：mock 修复回路（离线）

- 日期：2026-10-20
- 运行记录：`runs/m2-mock10.jsonl`（gitignored）、`runs/m2-mock.jsonl`（3 题版本）
- 模型：`MockModel`（`DEEPSEEK_*` 未配置 → 自动降级，记录里 `model = mock`）

## 这个里程碑要证明什么

**不是**「模型能提升成绩」，而是「回路能跑通」：第 0 轮级联 → 找出未解决题 →
逐题问模型 → 只把未解决的题重新拼成一个批次编译 → 按行号把诊断映射回题 → 落盘。

## 结果

10 题（与 M1 同一批）：

| 指标 | 值 |
|---|---|
| verified | **4 / 10（40%）** |
| 尝试次数分布 | `{1: 4, 2: 6}` |
| 失败类型 | `cascade_exhausted` ×6，`tactic_error` ×6 |
| token | 0（Mock 不产生 token） |

**与 M1 完全一致（4/10）。这是预期结果，不是缺陷。**

原因：`MockModel` 按轮次依次吐出 `rfl / simp / norm_num / linarith / nlinarith / omega / ring /
field_simp; ring / aesop`，这些**本来就都在第 0 轮的级联里**，所以它不可能比级联多证出题。
`MockModel` 的用途是让 runner、审计、日志在没有网络的环境下被完整测试。

`attempts` 直方图 `{1:4, 2:6}` 才是这一步真正要看的东西：4 题在第 0 轮解决（不再进入修复轮），
6 题进入第 1 轮并获得一次模型提议——说明「只提交未解决题」的分支被正确走到。

## 顺带验证到的四件事

1. **跨轮批量编译**：第 0 轮 10 题、第 1 轮 6 题，各一次编译，共 2 次（约 2×4 min）。
2. **部分批次审计**：第 1 轮只提交 6 题时，`_apply_audits` 必须跳过另外 4 题。
   这条早期会 `KeyError` 崩溃，已修并加了回归测试 `test_apply_audits_ignores_states_outside_batch`。
3. **记录 schema**：`attempts` 里逐轮保留 `source / status / error_kind / proof / compile_ms`，
   `pass@k` 可事后推导（ADR-0003）。
4. **降级逻辑**：没有 `.env` 时 `build_model()` 返回 Mock 并把
   `missing-config-fallback-mock` 写进运行记录，不抛异常、不中断。

## 未完成：真实 API 的一半

M2 的另一半（真实 DeepSeek）**当时被误判为「环境阻塞」**，实情是：

| 检查项 | 结果 |
|---|---|
| `api.deepseek.com` DNS | 正常解析 |
| 用 PowerShell `Invoke-WebRequest` 直连 | 报「基础连接已经关闭」 |
| 用 **Python `requests`** 直连（2026-10-20 晚补测） | **HTTP 401 `Authentication Fails`** —— 连得上，只是没 key |
| `github.com` / `baidu.com`（Python） | 200 |
| `.env` | 不存在 |

**结论：网络没问题，唯一缺的是 `DEEPSEEK_API_KEY`。**
之前所有探测都走 PowerShell 5.1 的 `Invoke-WebRequest`，它默认的 TLS 版本与现代站点
握手失败，报错和断网长得一模一样——这是本会话最值得记住的一个误判。

代码侧已就绪：`build_model()` 支持 `DEEPSEEK_PROXY`（或 `HTTPS_PROXY`），
配置模板见 [`.env.example`](../../.env.example)，`probe-api` 可先验证一次调用。

## 下一步

1. 开代理、填 `.env`，跑 `eval-llm --limit 10 --rounds 3 --network`，得到
   `cascade-only` vs `cascade + DeepSeek` 的真实对照。
2. 在真实模型数据到手之前**不要**做 M3（结构化 goal state）——否则无法判断增益来自
   goal state 还是来自「终于有一个能写 Lean 的模型」。
