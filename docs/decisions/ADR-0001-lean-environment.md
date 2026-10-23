# ADR-0001：Lean / Mathlib 编译环境与版本锁定

- 状态：**已迁移完成**（2026-10-22）——编译环境现在在本仓库的 `lean/`
- 影响范围：`harness/config.py`、`harness/leanenv.py`、`lean/`

> **迁移记录（2026-10-22）**：下面的「迁移计划」已执行。做法是把原工程
> `sgslean/.lake/packages/`（6 GB，含 `.git`）`robocopy` 到 `lean/.lake/packages/`，
> 再用一份只含 mathlib 及其传递依赖的 `lake-manifest.json`。
> `lake build` = 7890 jobs，**只重编译了 `Bench`**，Mathlib 的 olean 全部复用。
> `config.ENV_PROJECT` 已默认指向 `lean/`，**不再依赖外部仓库**。
> 副作用：单文件编译从 ~240 s 降到 ~67 s。
> 细节见 `lean/README.md`。

## 背景

P0 需要一个能编译 `import Mathlib` 的 Lean 4 环境。本机现状（实测）：

| 位置 | toolchain | `.olean` 数 | 根模块 `Mathlib.olean` | 可用 |
|---|---|---:|---|---|
| `C:\Users\gaosen\mathematics_in_lean\.lake\packages\mathlib` | v4.21.0 | 2687 / 6554 源文件 | **缺失** | ❌ `import Mathlib` 必然失败 |
| `D:\bianma\code\大创\sgs-reap\sgslean\.lake\packages\mathlib` | v4.28.0-rc1 | 7527 / 7520 源文件 | **存在** | ✅ |

同时，本机当时**无法确认可出网**：`github.com`、`lakecache.blob.core.windows.net`、
`api.github.com` 用 PowerShell 的 `Invoke-WebRequest` 探测均报「基础连接已经关闭」。
elan 已安装的 toolchain 为 v4.21.0 / v4.28.0 / v4.28.0-rc1 / v4.29.1 / v4.34.1。

## 决策

**锁定 Lean `v4.28.0-rc1` + Mathlib `v4.28.0-rc1`，通过 `lake env lean` 在
`D:\bianma\code\大创\sgs-reap\sgslean` 这个已有工程里编译。**

- 该路径由 `MINIF2F_ENV_PROJECT` 环境变量覆盖，默认值写在 `harness/config.py`。
- `harness/leanenv.check_env()` 启动时检查工程目录与 `Mathlib.olean` 是否存在，
  缺失时直接报错并指向本 ADR。

## 被否方案与原因

| 方案 | 否决原因 |
|---|---|
| 在本仓库 `lakefile.toml` 里 `require mathlib path=…` 指向 MIL 的 v4.21.0 | 两个问题叠加：① 那份构建不完整；② 即使完整，Lake 也要往依赖目录写 `lakefile.olean.lock`，触发权限拒绝 |
| 直接调用 toolchain 的 `lean.exe` + 手工拼 `LEAN_PATH` | 实测单次编译 **509 s**，比 `lake env lean` 还慢，且要自己维护 12 个包路径 |
| 让 `lake exe cache get` 重新拉 Mathlib | 当时判断为无网络；**该判断后来被推翻**，见文末「更正」 |
| 把整份 Mathlib 复制进本仓库 | 2.31 GB，且 git 依赖的 rev 校验要求连 `.git` 一起复制；收益只是「自包含」，暂不划算 |

## 后果

- **好处**：立刻可编译；v4.28.0-rc1 是唯一完整构建；与旧工程共用，不需要重建 2.3 GB olean。
- **代价**：本仓库对 `D:\bianma\code\大创\sgs-reap` 这个**外部路径**有依赖。
  该工程被移动或删除时，P0/M1/M2 全部不可用。已在 `check_env()` 里做成显式报错。
- **已知版本漂移**：miniF2F 上游 `leantoolchain` 声明的是 **v4.24.0**，与 4.28.0-rc1
  不同。部分题目可能因 Mathlib API 变动而无法编译。处理策略：**记录不兼容题号**，
  不修改题目文本（改题会破坏「与上游逐字一致」的评测前提）。

## 迁移计划（网络确认可用后）

1. 在 `lean/` 下建独立 Lake 工程，`lean-toolchain = v4.28.0-rc1`；
2. `lake exe cache get` 拉预编译 olean；
3. 把 `MINIF2F_ENV_PROJECT` 指向 `lean/`，`check_env()` 逻辑不变；
4. 本 ADR 追加「已迁移」记录，不删除历史。

## 更正（2026-10-20 晚）

**「无网络」是误判。** 用 Python 的 `requests` 实测：`baidu.com` 200、`github.com` 200、
`api.deepseek.com` 返回 **401**（说明连得上，只缺 API key）。

之前所有探测都用的是 PowerShell 5.1 的 `Invoke-WebRequest`，它默认的 TLS 版本
（TLS 1.0/1.1）与现代站点握手失败，报「基础连接已经关闭」，看起来和断网一模一样。

因此本 ADR 的**决策本身仍然成立**（当时确实没有完整可用的本地 Mathlib，
复用 sgslean 那份是最快路径），但「因为没网所以别无选择」这条**理由是错的**。
迁移到独立工程现在技术上可行，优先级不变（当前配置可用，迁移没有收益）。
