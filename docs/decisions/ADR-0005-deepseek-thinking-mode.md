# ADR-0005：DeepSeek V4 的「思考模式」必须关掉，否则回答永远是空

- 状态：已采纳（2026-10-20）
- 影响范围：`harness/models.py`、`.env.example`、`docs/research/`

## 现象

2026-10-20 第一次跑真实的 M2 对照（`easy` 档 60 题，`deepseek-v4-flash`，`max_tokens=1024`），
结果是 **35/60，和纯级联一模一样**——也就是说模型的 180 次调用**一次都没有产生有效证明**。

翻运行记录发现：每一轮的 `proof` 都是**空字符串**，而 `tokens_out` 恰好等于 `max_tokens`。
把原始响应打出来才看清：

| 字段 | 值 |
|---|---|
| `finish_reason` | `length` |
| `message.content` | `""`（空） |
| `message.reasoning_content` | 1933 字符（`max_tokens=1024` 时） |
| `usage.completion_tokens_details.reasoning_tokens` | 1024（全部） |

模型把**整个输出预算都花在推理上，一个字符的答案都没写就撞到上限**。

## 排查

三个模型、多种预算、多种开关，同一道题（`mathd_numbertheory_126`）：

| 配置 | finish | content | reasoning | 耗时 |
|---|---|---|---:|---:|
| `deepseek-flash`，4096 | length | 0 | 11794 | 19 s |
| `deepseek-v4-flash`，4096 | length | 0 | 10935 | 20 s |
| `deepseek-v4-pro`，4096 | length | 0 | 7219 | 53 s |
| `thinking: {enabled:false}` | — | HTTP 422：`thinking: missing field type` | | |
| `enable_thinking:false` / `chat_template_kwargs` / `reasoning_effort:low` | length | 0 | 6600–13034 | 19–21 s |
| `max_tokens: 16384` | length | 0 | **51314** | 78 s |
| **`thinking: {"type":"disabled"}`** | **stop** | **409** | **0** | **2 s** |

结论：**不是预算不够，是这套模型在思考模式下对这类 prompt 不会收敛。**
把预算加到 16384 也只是让它想更久，答案仍然是空。

## 决策

`DeepSeekClient` 默认发送：

```json
"thinking": {"type": "disabled"}
```

可通过 `.env` 的 `DEEPSEEK_THINKING=disabled|enabled` 覆盖；`enabled` 保留给
「以后想研究思考模式有没有用」的场景，但**不作为默认**。

模型名也按端点 `/v1/models` 的实际返回改成 `deepseek-flash`
（该端点只列出 `deepseek-flash` 与 `deepseek-v4-pro`）。

## 后果

- **好处**：单次调用从 19–78 s 降到 **1.3–2 s**，输出从 4096 token（全废）降到 **8–207 token**。
  Agent 回路第一次真正可用。
- **代价**：放弃了思考模式可能带来的推理增益。这是个**待验证**的取舍：
  如果以后发现某类题需要长推理，应该用「更大预算 + 后处理提取 content」的方式单独实验，
  而不是直接开默认。
- **对已有记录的影响**：`runs/m2-real.jsonl`（35/60）是**思考模式下的无效运行**，
  等价于「级联 + 空操作」。保留作为证据，但**不要**拿它当 M2 的结果。

## 顺带确认的 API 事实

- 端点：`https://api.deepseek.com/v1`，`/models` 返回 `deepseek-flash`、`deepseek-v4-pro`。
- 响应含 `reasoning_content` 字段（思考模式下才有内容）。
- 支持 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，说明有前缀缓存。
