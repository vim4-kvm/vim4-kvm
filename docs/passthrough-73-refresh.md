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

以下作为后续另行授权的执行计划。准备在持板前完成，首窗预计 28 分钟，22 分钟时进入恢复，
硬上限 30 分钟含恢复。完整产品缺项需先实现，再进入对应门禁。

| 时间 | 步骤 | 通过标准 |
|---|---|---|
| 持板前 | 完成同次 Image、DT、全模块、运行时与静态 PID1 的 manifest；离线 preflight；准备独立 RAM payload ID、恢复 proof 和测试脚本；源预置 SDR 动态帧号及合法 PCM | SHA/身份齐全，测试模式为 sink 所支持；预计任务可在 22 分钟内停止 |
| 0–3 分钟 | 记录当前 5.15 release/build ID、启动文件哈希、服务、UDC、OUT HPD/有效 EDID 与音频能力 | sink connected，真实 EDID 与目标模式匹配，默认恢复基线已确认 |
| 3–7 分钟 | 经 board-window 一次性 RAM 启动，读回 boot ID、候选身份、native KMS/VD1、TX 声卡/ELD | 全部匹配，无新增 oops/taint；失败立即进入恢复 |
| 7–10 分钟 | 桌面 KMS 图案与独立采集短并发，再有序释放桌面 KMS ownership | 两端内容推进、颜色和时序符合预期，无资源冲突；桌面与直通消费者按顺序占用 KMS |
| 10–17 分钟 | broker 原尺寸 SDR 1080p60，随后 sink 支持的 4K60，分别验证零远程客户端与 One-KVM H.265 并发 | 三高度动态帧号完整、采集 ERROR 为零、地址锁存随 vblank 推进、退休后 QBUF、CMA 有界；远程 framesDecoded 持续推进 |
| 17–20 分钟 | 一次受控源时序往返和一次已审阅的软件 connector 事件；记录完整恢复过程 | 相同时序无重复 modeset；新 generation 成功，旧帧不进新池；记录恢复秒数并与厂商同条件比较 |
| 20–22 分钟 | 若音频控制与分发已补齐，验证 RX/TX RUNNING、PCM 格式/ELD、队列和 XRUN；否则登记音频阻塞 | 静音不算音频通过；真实非零 PCM、远程与本地唯一 RX owner、恢复不重新 prepare TX。听感与 A/V 测量单列 |
| 22–28 分钟 | 停止本次消费者与临时覆盖，经 `board-window return-baseline` 正常重启恢复 | 5.15 身份、全部保护文件哈希、服务、UDC 和原有视频恢复，记录退出状态 |

任何 WARN/oops、帧撕裂、失控 modeset、CMA 不回收或 DMA 退休不明都立即停止该项并恢复。
回退遵循 [候选链与恢复](board-window.md#候选链与恢复)，保留 UART 与原始 proof。
候选依赖 RAM 启动选择，默认基线保持可直接 autoboot；正常重启失败时依既有看门狗恢复路径，
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
