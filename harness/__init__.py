"""大创2 的证明回路 harness。

分层：

* `config`      —— 路径、版本、超时、补救参数、计价等全局常量
* `leanenv`     —— 把多道题拼成一个 Lean 文件并编译（批量编译是性能关键）
* `diagnostics` —— 解析编译器输出（错误/警告/公理审计）
* `verify`      —— 判定「证明成功」的四项审计
* `problems`    —— 读取 bench 索引与题目文本
* `cascade`     —— L0 的 tactic 级联
* `models`      —— 可插拔模型后端（Mock / DeepSeek）
* `roles`       —— 角色 prompt 与解析（Planner / Critic / Strategist）
* `retrieval`   —— Loogle 引理检索（失败降级为空，不阻塞主循环）
* `runner`      —— 编译原语（分块、审计、落盘）与两阶段回路
* `metrics`     —— pass@k、耗时、失败分类
* `pipeline`    —— **阶段机**：L0 → 补救 → 计划 → L1×N，可扩 L2/L3
* `prover`      —— **对外接口**：`prove` / `prove_many` / `Budget` / `ProofResult`
* `worker`      —— **常驻 Lean 会话**客户端（一次导入，之后 0.2 s/题）
* `server`      —— HTTP 服务：`/health` `/check` `/prove`
* `goals`       —— 目标状态解析（**未接线**）
* `hints`       —— 诊断→对策提示（已证否，默认关闭，见 ADR-0006）
"""

__all__: list[str] = []
