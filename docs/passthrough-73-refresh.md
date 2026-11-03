# 7.3 直通正式基线同步与离线审查

2026-11-03。主仓与四个应用子仓在原 `passthrough-73` 工作树合并正式远端，
保留既有提交历史。内核通过 `tools/vm worktree new passthrough-offline --from origin/vim4-kvm-7.3`
登记新树 `~/src/linux-7.3-passthrough-offline`，构建目录为 `~/build/passthrough-offline`。
起点为 `4111568841bd83ca33b9b9a044ed9a7077f95004`，再合并旧透传分支。
本轮仅使用 heavy 构建票据。全部运行证据来自宿主或容器。

## 合并与修复

- 主仓正式起点为 `c50fc3563998faefdfda16db7ba7fc70dde3e424`。上板索引冲突保留双方条目。
- One-KVM 保留正式 `vim4v4l2src` 高帧率路径，显式 broker 模式使用 AppSrc。
  broker 的 NV12 输入拒绝原生 HDR 请求，避免 HDR source 独占打开 VDIN。
- NanoKVM broker 模式关闭 Main10 source 能力声明，走共享 NV12 source。
  `max-fps` 仅传给支持该属性的正式采集源，broker 后使用 `vim4ptsrate`。
  新增正常管线生成入口回归，覆盖 H.264、H.265、MJPEG。
- uStreamer broker 模式跳过独立 `vim4h265src`，保留普通路径的共享 HEVC 和高帧率行为，
  broker 后使用现有 PTS 限帧器。manager 正式更新自动合并。
- 内核 producer-layout 宿主夹具补齐正式 VDIN 的 `native_hdr` 状态字段，真实函数继续参与编译。

## 与 5.15 的覆盖对照

| 能力 | 当前 7.3 实现与离线证据 | 缺口或板上门禁 |
|---|---|---|
| 本地输出与采集并发 | 独立常驻 V4L2 owner、PRIME 导入、有限租约、reader fence 退休、跨代和慢消费者测试 | native VD1 与 VDIN/Wave5 的时钟、供电、CMA、真实读者退休待测。桌面 KMS 与采集并存也须独立验收 |
| 零客户端与应用切换 | broker 独立于应用，核心测试覆盖断连与有限 pending | JetKVM 尚未接入。三款已有适配的真实编码和切换仍待测，不能宣称四应用完成 |
| SDR 1:1 时序跟随 | SOURCE_CHANGE、HPD 去重、TEST_ONLY、中值/滞回、generation 重建 | 支持列表止于 60Hz，正式 hfr-yuv 的 120Hz 输入尚未纳入直通资格。1080p/4K 模式、色彩、60fps 扫描和切换恢复待测 |
| HDMI 音频 | AudioOwner 有界 PCM 队列、AlsaPump RX/TX 调用、RX 原句柄恢复测试 | audio worker 尚未接 service；ELD/动态速率协调、远程音频 IPC、应用音源接入及漂移控制缺失。现有应用与桥不能同时独占 RX |
| HDR | 读取活动 HDR2 映射事实，SDR NV12 保持 SDR 标签 | 原生高位深 scanout/元数据输出缺失；偏好执行与处理事实完整闭环未完成。PQ/HLG 真实颜色和 sink 组合待测 |
| manager | provider 区分 5.15 与 7.3，GET 只读 | broker `set` 明确拒绝，status 保持 unsupported。产品启停、持久偏好执行和安装启用尚未完成 |
| EDID 与恢复 | OUT 事件不主动重写 RX EDID，事件驱动重试 | 可选 sink/RX 能力交集 EDID 未实现；掉线后的实际黑屏/静音、重新锁定和旧池回收待测 |
| 延迟与性能 | 有软件租约及计数边界 | 未建立同条件 5.15 A/B/A。光学 glass-to-glass、扬声器延迟、A/V 偏差及长时帧节奏均待测 |

厂商对照分别为 [1080p 跟随](bringup/2026-10-25-vendor-passthrough-1080p.md)、
[音频](bringup/2026-10-25-vendor-passthrough-audio.md)、
[HDR 初期边界](bringup/2026-10-25-vendor-passthrough-hdr.md)。
1080p 记录给出约 5.844 秒控制恢复，音频记录给出 44.1/48k PCM、显示器可闻及 RX/TX 并发证据。
HDR 初期记录的原生输出缺口后来有双路径扩展，当前对照同时参照
[原生 HDR 双路径](bringup/2026-10-25-native-hdr-dual-path.md)。
厂商记录自身未证明完整光学延迟或所有听感指标，7.3 的离线通过也不补齐这些证据。

## 接上 HDMI-OUT 显示器后的验收清单

### 当前基线与候选形态

本节按协调者确认的当前默认 uhd7 修正，替代早版首窗中的 5.15 恢复目标。
来源锁为 [sources.toml](../packaging/kernel-edge/sources.toml) 的 `tested_build` 与
`retained_runtime.module_overlays`，实际部署证据见
[正式三模块更新](bringup/2026-11-03-mainline-modules.md)。恢复目标包含以下完整组合。

- `FullKvm` 默认项，`7.3.0-vim4kvm-uhd7+`，GPU 为 kbase。
- Image 源码 `52b95c8493264b195fe5fa10ccf07ad28670f16f`，build ID
  `d6f9c685802759c85cba6bd92bce90396d1cf6ec`，Image SHA256
  `10e3451d13bca87006bd93faa991c0290d0109df8a21f5bf0b4725f700f52354`。
- 已装 `t7_hdmirx`、`t7_vdin_test`、`wave5` 来自 `4111568841bd`，以来源锁中的
  压缩文件 SHA、加载 build ID 和部署收据为准；同时保留 kbase 三个外部模块及其身份。

候选计划采用 **uhd7 之上的临时 DT 与用户态覆盖**。对比 `52b95c8..4111568`，
运行时代码变化集中在上述三个已部署模块；透传分支另加 DT profile 和测试，
显示/ASoC 内建代码没有额外差异。因此首窗复用已验证的 uhd7 Image 和当前完整模块集，
候选改动集中在启用 native VD1/TX/split VCBUS 的 DT、broker 和应用适配。
以 passthrough DT 为底应用现有 kbase 选择/thermal 片段，关闭 Panfrost，重跑资源与 GPU
互斥预检；当前离线生成的 passthrough DT 尚未完成该 kbase 组合。

交付载体仍需可审计的独立 RAM payload 目录与 manifest，登记实际复用的 Image、包含
三模块更新的模块清单、候选完整 DTB、用户态覆盖和 PID1。DT 覆盖在启动时选择完整 DTB。
本轮 `pt-offline` 模块属于独立 release/新 vmlinux BTF 构建，只作离线编译证据；
将它们加载进 uhd7 会违反模块/BTF 匹配合同。首窗计划也无需为这组 DT/用户态改动重新构建
独立内核整包。5.15 保留为后续性能对照的测试对象。

### 窗口工具门禁

当前 [board-window](../tools/board-window) **尚不支持从 uhd7 完整执行本计划**。
`boot-candidate` 首次 proof 和 `BaselineCache` 要求 release 以 `5.15.` 开头；
[display-once.py](../packaging/kernel-edge/display-once.py) 的 `retained_preflight` 与
`cleanup_module_mountpoints` 同样限定 5.15，`prepare` 拒绝候选与 baseline 相同 build ID。
`return-baseline` 的身份比较可按 proof 检查任意 release，但清理仍被上述条件阻断，
且 `ready` 对 7.x 未强制检查 manager/HDMI 服务，现有成功退出条件不足以覆盖本次恢复标准。

持板前须完成针对此 uhd7 基线的工具适配与离线回归，范围为以下三项。

1. 首次 proof、保留基线检查和清理支持明确登记的 uhd7 身份，并保护 FullKvm 默认项、
   启动文件、运行时登记、当前模块文件/依赖清单及用户态覆盖目标。
2. 允许相同 Image build ID 的 DT 候选，以独立 payload ID、DTB/运行时哈希和新 boot ID
   区分候选与基线；验证当前运行 DT 的可读属性匹配候选，单看 uname/build ID 无法区分。
3. 恢复检查覆盖 uhd7 的 manager/HDMI/gadget、实际选定 KVM、kbase、三个更新模块的加载
   身份与视频推进。离线覆盖 uhd7 往返、同 Image 不同 DT、拒绝错误 proof/哈希、已有模块目录
   保留与临时覆盖退出恢复，并继续通过原有 5.15 回归。

以上工具适配、组合 DT 和新 payload 均为持板前待办，本次只修正文档。

### 首窗步骤与恢复

以下作为后续另行授权的执行计划。准备在持板前完成，首窗预计 28 分钟，22 分钟时进入恢复，
硬上限 30 分钟含恢复。完整产品缺项需先实现，再进入对应门禁。

| 时间 | 步骤 | 通过标准 |
|---|---|---|
| 持板前 | 完成上述工具适配/离线回归、kbase 组合 DT 与 uhd7 临时覆盖 payload；核对复用 Image/完整模块与候选 DT/运行时 manifest；准备恢复 proof 和脚本；源预置 SDR 动态帧号及合法 PCM | SHA/身份齐全，工具可按 uhd7 proof 完成往返，测试模式为 sink 所支持；预计任务可在 22 分钟内停止 |
| 0–3 分钟 | 记录当前 uhd7 release/build ID、FullKvm 默认项、启动/运行时文件哈希、三个更新模块与 kbase 身份、当前应用/服务、UDC、OUT HPD/EDID/ELD | 与上述来源锁及现场 proof 一致，sink connected，真实 EDID 与目标模式匹配 |
| 3–7 分钟 | 经适配并验证后的 board-window 一次性 RAM 启动，读回新 boot ID、候选 DT 属性、native KMS/VD1、kbase、TX 声卡/ELD及模块身份 | Image/模块保持已核定 uhd7 身份，候选 DT/用户态符合 manifest，无新增 oops/taint；失败立即进入恢复 |
| 7–10 分钟 | 桌面 KMS 图案与独立采集短并发，再有序释放桌面 KMS ownership | 两端内容推进、颜色和时序符合预期，无资源冲突；桌面与直通消费者按顺序占用 KMS |
| 10–17 分钟 | broker 原尺寸 SDR 1080p60，随后 sink 支持的 4K60，分别验证零远程客户端与 One-KVM H.265 并发 | 三高度动态帧号完整、采集 ERROR 为零、地址锁存随 vblank 推进、退休后 QBUF、CMA 有界；远程 framesDecoded 持续推进 |
| 17–20 分钟 | 一次受控源时序往返和一次已审阅的软件 connector 事件；记录完整恢复过程 | 相同时序无重复 modeset；新 generation 成功，旧帧不进新池；记录恢复秒数并与厂商同条件比较 |
| 20–22 分钟 | 若音频控制与分发已补齐，验证 RX/TX RUNNING、PCM 格式/ELD、队列和 XRUN；否则登记音频阻塞 | 静音不算音频通过；真实非零 PCM、远程与本地唯一 RX owner、恢复不重新 prepare TX。听感与 A/V 测量单列 |
| 22–28 分钟 | 停止本次消费者，退出临时覆盖，经适配后的 `board-window return-baseline` 正常重启回 FullKvm | uhd7 Image/build ID、基线 DT、三个更新模块、kbase、全部保护文件哈希与默认项匹配；原应用设置、manager/HDMI/gadget、UDC configured 和原有视频推进恢复 |

任何 WARN/oops、帧撕裂、失控 modeset、CMA 不回收或 DMA 退休不明都立即停止该项并恢复。
回退沿用 [候选链与恢复](board-window.md#候选链与恢复) 的 RAM 一次性选择和 proof 校验机制，
执行以本节列出的 uhd7 工具门禁通过为前提。保留 UART 与原始 proof。
候选依赖 RAM 启动选择，正常重启/autoboot 回到持久 FullKvm/uhd7，临时 bind 随重启退出；
恢复后核对完整模块更新身份，避免仅凭相同 release 判定恢复成功。正常重启失败时依既有看门狗恢复路径，
若仍无法恢复则保存证据并明确交接现场恢复需求。预留的 6 分钟是操作预算，硬件故障可能阻断完成。

后续每窗单独预计 25–28 分钟、含 6 分钟恢复。按顺序覆盖三应用切换与慢消费者、
补齐后的四应用与音频动态速率、HDR/EDID 组合、同条件 5.15 A/B/A。
每段稳定采样不超过 10 分钟，缺少光学/录音设备时保留对应未验项。

## 验证记录

原始日志位于本工作树 `logs/passthrough-offline/`。

- 主仓全套 519 项、18 跳过，其余通过；最终执行入口为
  `python3 -m unittest discover -s tests -p 'test_*.py'`。
- `kernel-build.log` 与 `kernel-modules.log` 为基于 uhd7 配置、独立 release
  `7.3.0-vim4kvm-pt-offline+` 的 `W=1` 构建。显示、RX/VDIN、Wave5、ASoC 目录和直通 DT
  编译成功，全量 2338 模块链接及 BTF 完成。全构建 1174 条编译警告，其中 1098 条为
  override-init；DT 另有 pinctrl 的 unit_address_vs_reg/simple_bus_reg 警告。
  相关目录首次定向 C 编译零警告。产物哈希见 `artifacts.log`。
  DT SHA256 为 `44bc65d48047c0085d4f5110aabb00b4ab545a6969a5cb49e19607d20594a087`。
  本轮未封装可启动部署包，现有 pt1 归档仍属于旧源码。
- `kernel-fixtures-final.log` 为 12 个显示/采集/音频 host fixture 及真实 DT 资源预检通过；
  `wave5-host.log` 为 12 个 Wave5 host fixture 通过。KUnit 和真实 DMA 设备集成未运行。
- `linux-final-retry.log` 为 broker Linux 32 项全部通过，包含真 GStreamer、seqpacket、
  SCM_RIGHTS 和最终 GstMemory 释放 ACK。内存为文件后备，未使用 VDIN/VD1 硬件。
  同一记录中 NanoKVM VIM4 Go 全套和 uStreamer VIM4 核心构建通过。
  `ustreamer-final.log` 为补充 broker 分支后的两项 C 宿主回归通过。
- `onekvm-retry.log` 为 Rust 835 通过、4 忽略；`linux-retry.log` 中 One-KVM 助手 45 通过，
  manager Go 全套与 vet 通过，manager Python 233 项、12 跳过，其余通过。
- 首轮失败完整保留。包括容器自定义入口、缺 GI/JPEG/PTS 插件、手工构建插件缺 PACKAGE、
  缺 fixture 参数及 `native_hdr` 字段、MJPEG 软件上限测试期望不准确。
  环境补齐、期望修正后重跑通过。NanoKVM HID 测试曾报 `interrupted system call`，
  原样复跑通过，未修改 HID 代码或绕过测试。

本轮各子仓最终提交如下，正式基线通过 merge 保留。

| 仓库 | 正式基线 | 本轮提交 |
|---|---|---|
| 主仓 | `c50fc3563998faefdfda16db7ba7fc70dde3e424` | 首次合并 `698a231` 后再合入该正式基线，本文单独提交 |
| NanoKVM | `b1e1576a440a02c81454af5f131bf3f87aa4b73c` | 合并 `1a44afee51b68dae5072df8f8c053f1cd28bfd40`，修复 `984a6813e5827cef67812646f1345bf86348d1a3` |
| One-KVM | `ca2292b1aaf4258963ebdabc929384a68b0c82fa` | `0b241b364ce700646596a2aaeb5e561e610eee67` |
| uStreamer | `4cc240747f1863439ff9e1263fd3eb1803fee39f` | `20c418a7a5e5fad412df5791914479e4271e127a` |
| vim4-manager | `fbd8933fee7d95c879560aab5abd874acdfc0500` | `44dd8233ffd1f26774b6eb635e2f785fc0aa11e3` |
| 内核 | `4111568841bd83ca33b9b9a044ed9a7077f95004` | 合并 `5f5f999d3901a2fb945aab33eae4ea941488bbb9`，fixture 修复 `e5e9dc26da21327d4d5b54ef94a27af6ea4714ba` |
