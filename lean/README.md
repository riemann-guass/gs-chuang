# lean/ —— 本仓库自己的 Lean 工程

2026-10-22 起，`lean/` 是一个**完整可用的 Lake 包**，内含 Mathlib（`v4.28.0-rc1`），
`harness` 的编译环境就指向这里。**不再依赖** `D:\bianma\code\大创\sgs-reap\sgslean`。

## 目录

```
lean/
├── lean-toolchain          # leanprover/lean4:v4.28.0-rc1
├── lakefile.toml           # name = bench；require mathlib v4.28.0-rc1
├── lake-manifest.json      # 9 个包（mathlib + 8 个传递依赖），rev 已固定
├── Bench.lean              # `import Mathlib`，保证工具链可用
├── Worker.lean             # **常驻 worker**：一次导入 Mathlib，之后按文件协议服务
├── Probe.lean              # 冒烟
├── ProbeTactic.lean
├── README.md
├── .lake/packages/         # 6 GB，gitignored —— 从已有构建复制，未重新编译
└── Bench/                  # 派生物，gitignored
    ├── Valid/<id>.lean     # 244 题，上游原样复制
    ├── Test/<id>.lean      # 244 题
    ├── index.jsonl
    └── _work/              # 运行时批次文件
```

## Worker.lean（常驻会话）

```powershell
$env:WORKER_DIR = "Bench\_work\_worker"
lake env lean Worker.lean      # 首次 60–65 s，之后常驻
```

协议：客户端往 `WORKER_DIR` 写 `req_<seq>`，worker 写 `rsp_<seq>`。
Python 侧封装在 `harness/worker.py`，详见 `docs/decisions/ADR-0009-lean-worker.md`。

**注意**：它**永远不会编译结束**（`run_tac` 里是死循环），所以不要加进库目标。

## 这个 Mathlib 是怎么来的

本机原先只有一份**完整**的 Mathlib 构建，在另一个仓库里。直接 `require` 那个路径
不行——Lake 会往依赖目录写 `lakefile.olean.lock`，跨出工作区就被拒。

所以用 `robocopy` 把那边的 `.lake/packages/`（6 GB，保留 `.git` 与时间戳）复制到本目录，
再写一份只含 `mathlib` 及其传递依赖的 `lake-manifest.json`。

`lake build` 的结果：**7890 个 job，只重新编译了 `Bench`**（542 s），
Mathlib 的 ~7500 个 olean 全部直接复用，**没有触发重建**。

## 验证

```powershell
cd lean
lake build                                   # 应显示 Built Bench
lake env lean Bench\_work\foo.lean            # 单文件编译，实测约 67 s
```

`python -m harness.cli check` 会检查
`lean/.lake/packages/mathlib/.lake/build/lib/lean/Mathlib.olean` 是否存在。

## 注意

- `.lake/` 是 **6 GB**，已 gitignore。换机器必须重新准备（`lake exe cache get` 或复制）。
- 不要删 `lake-manifest.json`，否则 Lake 会要求 `lake update` 并可能尝试联网。
- `Bench/Valid`、`Bench/Test` 是 `scripts/gen_bench.py` 生成的派生物，也不入库。
