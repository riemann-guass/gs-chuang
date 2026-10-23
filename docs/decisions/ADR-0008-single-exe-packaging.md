# ADR-0008：产品分发形态 —— 单 exe 方案**不可行**，回到「olean + 常驻进程」

- 状态：**已否决（单 exe）**，2026-10-23。常驻进程部分已由 **ADR-0009** 实现并验证
- 影响范围：产品化方案、`lean/`、ADR-0007（常驻会话）

## 当初的设想

把 Mathlib 编进一个可执行文件，用户只下载一个 exe，启动即用，不需要 olean、
不需要 Lake、不需要工具链。实测这个 exe：

| 指标 | 实测 |
|---|---|
| 产物 | 206.8 MB 单文件 |
| 启动到就绪 | **1.9 s** |
| 热态 stdin/stdout 往返 | 0.1 – 9 ms |
| 空目录（无工程、无 olean）能否运行 | **能** |

看起来完美。但这是**运行已编译代码**的能力，不是**elaborate 新代码**的能力。

## 决定性实验

写了一个探针 exe，在 `main` 里直接调用：

```lean
let env ← importModules #[{ module := `Mathlib, importAll := true, isExported := true }] {}
```

结果（空目录与工程目录都一样）：

```
importModules: FAIL  unknown module prefix 'Mathlib'
No directory 'Mathlib' or file 'Mathlib.olean' in the search path entries
```

**exe 里没有 olean，也拿不到 Environment。** 它启动快的原因正是
「只执行链接进来的机器码」，而 elaboration 必须要有 Mathlib 的**声明环境**，
那是 `.olean` 里的数据，不是链接进二进制的代码。

所以：**单 exe 方案不能用来做定理检查**。它只能当启动器 / UI 外壳。

## 结论：回到「olean + 常驻进程」

产品载荷仍然是：

| 组成 | 体积 | 说明 |
|---|---:|---|
| Mathlib olean（7527 个） | 1.75 GB | **必需**，elaboration 的前提 |
| 8 个依赖包的 olean | 0.37 GB | 必需 |
| Mathlib 源码 | 0.08 GB | 建议（报错定位） |
| Lean 工具链 | 数十 MB | 必需 |
| ~~`.git`~~ / ~~`.lake/build` 元数据~~ | ~~4.3 GB~~ | **不需要**，已排除 |

合计 **≈ 2.2 GB**（压缩后估计 600–800 MB）。首启预热 = 一次 olean 载入，
实测 60–240 s（受机器与磁盘缓存影响很大）。

## 于是「轻量」只剩三个真正有效的杠杆

1. **常驻进程**：载入一次，之后每次检查亚秒级（ADR-0007 的 worker）。
   这是「每次都要等」和「只等一次」的差别。
2. **裁剪 Mathlib**（路线 C）：用 `importGraph` 算目标题集的依赖闭包，只编这些模块。
   估计能到 15–30%（未实测），载入降到 10–20 s、载荷降到 ~0.5 GB。
   这是**唯一能同时降低载荷和预热时间**的手段。
3. **首启后台预热 + 降级**：App 启动即在后台起 worker，UI 立刻可用；
   预热失败退回批量模式（慢但能出结果）。

## 这次实验的净收益

- 确认了**哪些路走不通**：单 exe 不行、进程内 `runFrontend` 不行（旧工程已记录）、
  LSP 完成信号不稳（ADR-0007）；
- 确认了**必须走**的路：`lean` 进程 + olean + 一次导入后常驻；
- 拿到了一个可用于 UI 的副产品：**任意 Lean 工程都能编出 200 MB 级 exe、启动 1.9 s**，
  以后做「本地启动器 / 安装器 / 离线演示」可以直接用。

## 下一步

写真正的 worker：一个 `.lean` 文件用 `run_tac` 跑常驻循环（旧工程 `sgslean` 已验证这个
模式在 v4.28 可用），由 `lean worker.lean` 启动，一次导入 Mathlib 后按 JSONL 服务请求。
验收标准见 ADR-0007 末尾（连续 10 个文件 < 15 s、诊断与批量一致）。
