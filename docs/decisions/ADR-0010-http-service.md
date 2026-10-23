# ADR-0010：把引擎包成服务（`serve` + `/check` + `/prove`）

- 状态：可用，2026-10-23
- 影响范围：`harness/server.py`、`harness/cli.py`（`serve` 子命令）
- 依赖：ADR-0009（常驻 worker）

## 为什么

前面所有东西都是「跑一批题」的脚本。要给外部用（App、别的程序），需要一个
**长驻进程 + 请求/响应接口**，否则每次调用都要付 60 s 的 Mathlib 载入。

一条命令：

```powershell
python -m harness.cli serve --port 8080            # 只做验证（L0 级联）
python -m harness.cli serve --port 8080 --rounds 2 --network   # 带上模型修复
```

## 接口

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | `/health` | — | 预热耗时、请求计数、模型状态 |
| POST | `/check` | `{"statement": "...", "proof": "..."}` | `ok / goals / sorry / reason / error / latency_ms` |
| POST | `/prove` | `{"statement": "..."}` | `ok / proof / stage / latency_ms / rounds`（+tokens） |

`statement` 可以是 `theorem ...`、`example : ...`，也可以只给命题
（服务端自动补 `example :`）。

## 实测

```
HEALTH  {'ok': True, 'warmup_s': 62.7, ...}
PROVE   {'ok': True, 'stage': 'L0', 'latency_ms': 63}
CHECK   ok=True   43 ms   theorem t (n : Nat) : n + 0 = n   | rfl
CHECK   ok=True   64 ms   theorem t (n : Nat) : n + 0 = n   | simp
CHECK   ok=True  110 ms   theorem t (a b : ℂ) : a + b = b + a | ring
CHECK   ok=False   63 ms  example : (1:Nat) = 2             | rfl
CHECK   ok=True   93 ms   (1:Nat) + 1 = 2                   | norm_num
```

## 一个必须写清楚的约定：**不要自己 `intro`**

worker 会像真正的声明一样，先把 `theorem t (n : Nat) : ...` 里的参数
**引进局部上下文**，然后才证明。所以：

```lean
theorem t (n : Nat) : n + 0 = n := by rfl     -- ✅ 对
theorem t (n : Nat) : n + 0 = n := by intro n; rfl   -- ❌ 报 "no additional binders"
```

这与批量编译的行为一致（批量编译里参数也是局部假设），但和「把语句当 ∀ 命题」
的直觉不同，所以在这里写明。

## 诊断通道（G3）

失败原因现在会带回**可读的目标状态**（保留 Unicode）：

```
⊢ arg✝¹ = 11
arg✝² arg✝¹ : ℂ
arg✝ : arg✝² + arg✝¹ = 7
```

实现要点：响应统一用 `Json.compress` 序列化（不手写字符串拼装），
消息按**字符**截断（`toList.take`，不用 `String.take`），
从而避开 Lean 4.28 对多字节字符串做切片时的 panic。错误按
`classify_worker_error` 归成与批量编译一致的类别（`cascade_exhausted` /
`unsolved_goals` / `type_mismatch` / `max_rec_depth` …），L1 下一轮能直接用上。

## 限制

- **单线程**：`HTTPServer` + 一个 worker，一次只能处理一个请求。
  并发要起多个 worker 进程，不在本版范围。
- `--rounds` 需要 `--network`，否则退化到只试 L0。
- 没有鉴权、没有限流。**只能监听 127.0.0.1**，不要直接暴露到公网。
