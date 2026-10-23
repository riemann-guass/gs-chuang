# ADR-0002：模型后端抽象与「离线优先」

- 状态：已采纳（2026-10-19）
- 影响范围：`harness/models.py`、`harness/runner.py`

## 背景

调研结论（见 `docs/research/multi-agent-atp-survey.pdf` §4.4、§6.4）：

- DeepSeek Flash 一类模型强于**非形式数学**（AIME 2026 96.7%）、弱于**Lean 语法与库内定位**；
- 因此它在回路里应当扮演「提议 / 诊断 / 修复」，而不是「一次写完整证明」；
- 但当时（据称）本机网络不可用，真实 API 随时可能调不通。

> **更正（2026-10-20 晚）**：网络其实是通的，之前的「断网」是 PowerShell 5.1 的
> TLS 默认值导致的误判（见 ADR-0001 文末）。真实 API 唯一缺的是 key。
> 下面「离线优先」的设计**保留**——它依然是好的工程约束（不依赖外部服务即可回归），
> 只是不要再用「没网」当理由。

如果让整条回路依赖 API，那么每次断网都会让 P0/M1 停滞。

## 决策

1. **`ModelClient` 是一个 Protocol**，`runner` 只依赖 `propose(req) -> ModelResponse`。
2. **`MockModel` 是一等公民**：确定性、零成本、离线，按轮次依次吐出级联里的下一个
   tactic。它不负责「证出题」，只负责让 runner / 审计 / JSONL 在没有网络的情况下
   能被完整测试。
3. **`build_model()` 自动降级**：`.env` 缺 `DEEPSEEK_BASE_URL` 或 `DEEPSEEK_API_KEY`
   时返回 `MockModel`，并把原因写进运行记录（`missing-config-fallback-mock`）。
   **不抛异常、不退出**——降级是预期行为，不是错误。
4. 不引入 `openai` SDK（本机未安装且无法联网安装），直接用 `requests` 打
   OpenAI 兼容的 `/chat/completions`。

## 配置项

`.env`（已 gitignore）：

```
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 后果

- 好处：P0/M1 完全不依赖网络；M2 的 mock 模式可在 CI 里回归；A/B 对照不需要花钱。
- 代价：`MockModel` 的输出与真实模型的分布完全不同，**不能**用它得出的成功率
  推断真实系统表现。所有 mock 运行的记录里 `model` 字段都是 `mock`，评测报告必须
  显式区分。

## 待验证（M2 的第一件事）

真实 API 的以下行为**尚未验证**，不能当作已知：

- 工具调用 / JSON 结构化输出在长上下文下的稳定性；
- 单轮能稳定产出的 Lean 代码长度；
- 每百万 token 的实际计费、延迟、是否有缓存折扣。
