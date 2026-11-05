# 2026-11-05：解码分支迁到集成基线

56 个解码提交已无冲突 rebase 到集成基线；range-diff 全部为 `=`。
逐提交模块、内建和有效 sparse 检查通过；引入 KUnit 后的 17 个提交各自实际
运行 QEMU 测试并通过。尚未据此宣称新基线硬件验收完成。

## 源码与验证边界

| 身份 | 完整提交 |
|---|---|
| 原分支基线 | `2662456a1a636f668454ab04a1c63f567206a592` |
| 原解码 HEAD（`.27`） | `02a3b188757e5ece5a0670681bab43d662d9d271` |
| 新集成基线 | `fd41fb5950b9da1fb336ce00d5137d27ee9755fa` |
| 重放后的解码 HEAD | `960132382e00864f4944aee077cd621927a97bb0` |

原分支已由协调者保存在 `origin/hwdecode-parity-pre-rebase-73`；本次只重放提交，
未改补丁内容、作者或历史正文。未提交 HEVC 草稿继续隔离保存，不参与重放。
旧基线 [r49](2026-11-05-vdec-field-lifetime.md) 和
[r50](2026-11-05-vdec-sharp-tail.md) 的结果不算新基线验收。

原始输出在 `build/hwdecode-parity/rebase-integration/`：

- `range-diff.log`：56 个条目全部相同；`rebase-resume.log`：重放过程。
- 每个 `NN-完整提交` 前缀的 `identity`、`source.sha256`、`module.log`、
  `builtin.log`、`done`：逐提交身份、源文件哈希和实际构建结果。
- 第 40–56 个提交的 `kunit.json`、`kunit.log`、`qemu.log`：每次运行的
  QEMU 原始输出；`verification-summary.json` 汇总实际计数。
- `bindings.log`：`media/amlogic,t7-vcodec-dec.yaml` 的 dt_binding_check。

模块检查使用生产配置及 `VIDEO_AMLOGIC_VDEC=m`；早期内建检查使用同一生产
配置把该驱动改为 `y`。第 1–39 个提交没有 `.kunitconfig`，明确记为不适用，
没有运行历史 Python/mock fixture。引入 KUnit 后按对应提交的配置运行 ARM64
QEMU，并在该内建配置上重跑 W=1/C=2；检查日志中实际存在 sparse CHECK 行。

| 重放序号 | KUnit 通过数/总数 |
|---|---|
| 40 / 41 / 42 / 43 | 3/3、5/5、10/10、12/12 |
| 44 / 45 / 46 / 47 | 各 17/17 |
| 48 / 49 / 50 / 51 | 18/18、19/19、20/20、22/22 |
| 52 / 53 / 54 / 55 / 56 | 22/22、23/23、24/24、25/25、25/25 |

最终 vdec 模块/内建均无自身诊断；内建前置仍有既有的 ARM64
`__kernel_getrandom` sparse 声明告警。早期版本的历史诊断保留在各自日志，
不将全系列描述成零告警。最初尝试把后期最小 KUnit 配置用于第一个提交，
因早期尚未 select REGMAP_MMIO 而失败；修正为生产配置内建验证后逐提交重跑，
保留 `first-builtin-minimal-config-failed.log`。没有为通过检查修改旧提交代码。
dt-schema 使用既有 `build/dt-schema-venv`；最初 PATH 未包含工具的失败日志也保留。

## 下一候选的证据计划

复用 `vdec-sequence` 源码工作树和 O=，构建生产配置 `.28` 原生整包。
新候选只使用已提交源码，不装 HEVC 私有草稿；本轮不触发 HEVC 解码。

构建封包与 VM/Mac 两端哈希核对完成。r51 启动冷复位，解码验收全部未运行，
已恢复 `.3`，见[启动记录](2026-11-05-vdec-r51-coldboot.md)：

| 产物 | 身份 |
|---|---|
| release | `7.3.1-vim4-20261105.28` |
| Image build ID | `81bb2f999ffffb38d549afbf8b15fb3048184c0f` |
| config SHA-256 | `7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c` |
| Image SHA-256 | `14f6d614f7a7b0e0f9852c59af95d6f0f7f73c52c5f351e0db888e094824f50a` |
| manifest SHA-256 | `ae038a11041a278bf5892ba2829e7e751374a1a1f6c0804915eee96c1686983b` |
| RAM archive SHA-256 | `ba4fa4a3bb0aa3850049c3cd3dab99431564cc1c4dbc96af3c2fc9bd70b13092` |

证据为 `rebase-integration/candidate-build.log`、`run51/artifact-identity.json`；
配置与正式 `kernel.config` 相同。匹配 Image 的原生模块随包加载。

先补 stateless streaming compliance，再记录两条 Sharp 的 GStreamer 日志、
V4L2 QBUF/DQBUF 与 vb2 提交/完成事件，保留原始输出并核对长度。
事件使用独立 tracefs instance，仅点名码流启用，结束或超时时均保存并清理。
最后按预算分窗跑 H.264 全集；普通像素 Fail 收集后继续，Timeout 或内核异常
立即收尾。全部按 FIFO，恢复窗口进入时确认的正式基线并验证 KVM 视频。
