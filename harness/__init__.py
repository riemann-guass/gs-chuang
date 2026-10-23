"""大创2 的证明回路 harness。

分层：

* `config`      —— 路径、版本、超时等全局常量
* `leanenv`     —— 把多道题拼成一个 Lean 文件并编译（批量编译是性能关键）
* `diagnostics` —— 解析编译器输出（错误/警告/公理审计）
* `verify`      —— 判定「证明成功」的四项审计
* `problems`    —— 读取 bench 索引与题目文本
* `cascade`     —— L0 的 tactic 级联
* `models`      —— 可插拔模型后端（Mock / DeepSeek）
* `runner`      —— 单轮/多轮回路与 JSONL 落盘
* `metrics`     —— pass@k、耗时、失败分类
"""

__all__: list[str] = []
