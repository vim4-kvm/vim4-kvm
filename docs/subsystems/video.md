# 音视频

5.15：RX port1→VDIN0→vfm_cap DMA→amlvenc→WebRTC；video71普通模式为回写。
7.3 [uhd4](../bringup/2026-10-31-uhd4-formal-smoke.md)：HDR2 PQ→709 NV12→DMA→Wave5；HLG已实现无真源未验。

## HDMI 显示器行为

默认把 VIM4 当作一直连接的显示器：HDMI 接收服务与浏览器会话独立，
没有观看者时仍保留所选 EDID 和显示器连接。HPD 表示接收端存在，
不能保证发送端持续输出画面，也不能强制主机退出休眠或虚拟显示器模式。

| 事件 | 预期行为 |
|---|---|
| 网页刷新、连接或断开最后一个观看者 | 只管理推流会话；不改 EDID、不脉冲 HPD、不重启 HDMI 接收服务 |
| 更换编码格式、码率或采集缩放尺寸 | 只调整采集/编码；不改变主机看到的显示器能力 |
| 应用重启，接收端仍加载相同 EDID | 保持显示器连接；恢复操作应幂等 |
| 用户更换 EDID | 写入新能力并重新协商；允许短暂黑屏和主机重新排列显示器 |
| 用户明确要求重新连接显示器 | 允许热插拔脉冲；不把该操作绑定到普通网页刷新 |
| 主机停止输出、休眠或切换虚拟显示器 | 保留显示器连接，区分无信号与采集故障；不周期性重写 EDID |

JetKVM 的“空闲时隐藏显示器”是用户主动选择的例外，默认保持关闭。
切换应用时若两者保存的 EDID 不同，可能需要一次重新协商；这不等同于
网页会话变化，不能把应用切换的 EDID 恢复放进每次连接路径。

静止画面不能作为故障判据。持续收到或解码 60 fps 也不能证明画面内容在更新。
5.15的[信号变化恢复](../bringup/2026-10-27-signal-recovery.md)使用RX缓存锁定位，
确认输入变化后只重建采集/编码、保留WebRTC连接；正常重建跳过故障退避，
约束VDIN1池预算，防止反复切换时连续内存不足。HDMI重新同步仍会中断源端新帧。
若需要自动恢复，先分辨 HDMI 信号锁定、采集帧推进和浏览器解码各自的状态，
优先恢复故障环节；不能根据像素不变自动热插拔。

验收时分别记录 HDMI 服务运行实例、EDID/HPD 变更日志、输入锁定和浏览器解码状态：
覆盖无观看者、连续刷新、重新连接、应用重启和主机休眠恢复。
使用物理 HDMI 桌面上的运动标记验证内容更新，不能用虚拟桌面上的标记代替。
虚拟显示器退出后的恢复还需单独复测；切换 EDID 后恢复只说明重新协商有效，
不能据此确定故障在主机还是 VIM4。上述内容是行为约束，不代表所有场景已通过硬件验收。

## HDR 输入

HDR 的全局默认、原生双路径、插件部署顺序及验证边界见 [HDR 输入映射](../hdr.md)。
5.15远程HDR与7.x的HDR→SDR映射须分别验收。
[7.3原生HDR门禁](../hdr10-remote-73.md)。

## 按改动范围读取

- [新内核基线](../kernel-edge.md#相关记录)：7.x 采集、编码、HDMI、音频及故障恢复的历史证据。
- [延迟测量](../latency.md#相关记录)：软件端点、VBV、发送候选与当前延迟复测。
- [播放差异调查](../kvm-delay-causes.md)：同步组、队列、媒体时钟及未决问题。
- [RTP 发送审查](../rtp-send-optimization-audit.md)、[编码库审查](../encoder-fast-packing-audit.md)：发送后端、编码 ABI 与硬件验证边界。
- [高刷审查](../1080p120-audit.md)、[VRR 准备](../vrr-preparation.md)：分别核对远程输入与本地输出能力。
- [驱动基准](../driver-benchmark.md)、[本地视频基准](../local-video-benchmark.md)：按测量端点选择工具。

- [采集插件](../../gst-plugin-vfmcap/README.md)：格式和 DMA-buf 生命周期。
- [编码插件](../../gst-plugin-venc/VIM4.md)：帧率预算、安装和测试。
- [应用与音频](../../NanoKVM/VIM4.md)：功能覆盖和构建。
- [视频配置](../../NanoKVM/deploy/vim4/VIDEO.md)：RTP、码率、GOP。

HDMI 启动脚本默认使用完整帧低延迟模式（VDIN mask 0x3）；
HDMI_LOW_LATENCY=0 恢复厂商自动策略。模式含义、对照结果及帧一致性检查见 [测量文档](../latency.md#board-side-isolation-and-completed-frame-mode)。

编码器测试不能与应用或其他任务并发占用硬件。
验证区分静止/运动、分辨率/帧率切换、热插拔、重连和丢包恢复。
记录版本、配置、负载；帧率、吞吐量和端到端延迟分别报告。

## 4:4:4 采集

`HDMI_CAPTURE_FORMAT=YUV444` 是共享 HDMI 服务的可选格式，原始采集与 CPU 重排可达
4K60，但现有硬件编码只输出 4:2:0，应用仍用 NV21。改采集格式、vfm_cap 映射或
真彩编码前读 [4:4:4 采集](../capture444.md)。

## Wave5 隔离告警

复位失败后必须保留 DMA 内存与映射，直到重启清除隔离。监控服务默认只记录告警；
自动重启必须确认全部 KVM 应用停用且虚拟介质为空，不能把 One-KVM 空闲视为没有消费者。
状态接口、计时条件、部署与回退合同见[隔离告警说明](../kernel-edge.md#wave5-隔离告警)。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| vb2前置元数据使跨回调代号错位 | 保持vb2首成员并加编译断言；独立export不能用inode关联，cleanup不等于编码完成 | [HDR2回归](../hdr2-dma-contract.md) |
| 见到 `last_wr_vfe` 就认为已完成图像多等一帧 | 当前 VDIN1 RDMA 提前一拍提交地址、下一拍执行、再下一拍交付。匹配实际缓冲与 pending/已执行表；寄存器 DMA 完成不能当图像写完 | [逐缓冲核实](../bringup/2026-10-25-vdin1-frame-handoff.md) |
| 7.x JPEG DMA 导入触发 reservation-lock WARN | 新内核 map/unmap_attachment 要求调用者持锁；使用对应 unlocked helpers 管理锁，不忽略 taint 后继续验收 | t7-jpeg/test_import.py、[MJPEG 记录](../bringup/2026-10-21-edge-scaling-jpeg.md) |
| 切分辨率后没有视频 fd，仍残留一组 CMA 分配 | GStreamer 先停用池，STREAMOFF 后另一个线程归还缓冲仍可 QBUF，随后 orphan 已无流可冲刷。先停止获取，在 QBUF 锁内停流并完成 orphan，再停用池；仅关闭 last-sample 缓存不足以修复 | packaging/kernel-edge/test_gstreamer_orphan.py、[动态模式记录](../bringup/2026-10-20-edge-dynamic-modes.md) |
| 7.x 无周期 IDR，仍每约 250ms 短顿 | ENUMINPUT 误用双次稳定检查，持有采集 ioctl 锁等待 20ms。实时状态使用即时读取并清除旧状态，STREAMON 保留稳定性资格检查；仅将应用查询移到另一线程仍会争用队列锁 | t7-hdmirx/test_core.py、[状态查询实测](../bringup/2026-10-20-edge-status-latency.md) |
| 7.3 网页反复重配后 CMA 耗尽，分配失败又触发 Oops | GStreamer 1.24.2 每帧遗漏输入池 unref，空 LAST 缓冲也未归还；另有 Wave5 辅助 DMA 局部副本和实例重复释放。插件和驱动分别修复，SET_FB 后保留 DMA 直到固件停止；每轮检查 fd/CMA，不能只看进程退出后的空闲内存 | tools/wave5-lifecycle-check.py、[应用接入](../bringup/2026-10-20-onekvm-wave5.md) |
| 原始 720×400 正常，Wave5 DMA 导入 QBUF 返回 EINVAL | VDIN 的 16 字节行对齐不足以满足 Wave5 协商得到的 32 字节 RAW 行宽。NV12 采集按 32 字节补行、保留可见宽度，UV 偏移和两平面导入使用实际 stride；同时检查高度补齐后的容量 | [输入模式覆盖](../bringup/2026-10-22-edge-hdmi-modes.md) |
| H.264 第一次强制 IDR 有效，后续请求不再产生 IDR | Wave5 用 HEVC NAL 19/20 判定所有格式，AVC NAL 5 未标为 V4L2 KEYFRAME，GStreamer 保留未完成请求。按编码格式报告帧型；用长于整段测试的 GOP 连续请求并核对输出 | tools/hdmirx-encode-check.py --keyframe-at、[应用接入](../bringup/2026-10-20-onekvm-wave5.md) |
| 原始 DMA 采集 60fps，但全帧 CPU 处理只有约 13fps | write-combine 映射下读一帧 4K 需约 55.6ms，SIMD 无法弥补。改为只读可缓存映射并实现 DMA-BUF CPU 访问同步，融合复制与重排，复用输出缓冲；必须逐帧验证动态标记与单像素色度，不能只测重复读取同一帧 | common_drivers/drivers/media/vfm_cap/test_lifecycle.c、gst-plugin-vfmcap/tests/capture-integrity.c |
| 给 cached DMA 环只做每轮复制同步，遗漏首次交给设备的同步 | dma_alloc_noncoherent 的分配器会通过 CPU 映射清零；首次 DMA 前也必须 sync_for_device，每轮复制保持 CPU／设备所有权交接 | [7.3 私有 DMA 环](../bringup/2026-10-19-hdmirx-dma-ring.md) |
| 30fps 编码预算配 60fps 输入 | 旧 amlvenc 造成实际码率偏大。修正插件并传入输入帧率；预算不是采集节奏 | gst-plugin-venc/VIM4.md |
| 用 game_mode 0 当作关闭低延迟的实验对照 | 0 恢复自动策略，实际模式可能是 0xb。核对驱动 state 中的当前模式，不能仅看全局参数；完整帧模式使用 0x3 | [采集延迟对照](../latency.md#board-side-isolation-and-completed-frame-mode) |
| 把 stock video71 当 HDMI 输入 | 原厂 vdin1 默认输出回写；新增原生 HDR 双路径显式共享主 RX 才是例外，普通采集仍用 vdin0 → vfm_cap | [硬件](../hardware.md)、[双路径交付](../bringup/2026-10-25-native-hdr-dual-path.md) |
| HDMI 有音频包、WebRTC 已连接但始终静音 | TDM-B 默认读外部引脚。HDMI 服务 ExecStartPre 在 ALSA restore 后选 hdmirx，再允许 NanoKVM 启动；零峰值录音不能证明声音正常 | [功能与音频状态](../archive/feature-status.md)、packaging/ubuntu/check-audio-startup.py |
| GE2D 缩放单次成功，切编码后进程报 safe_close EBADF | 厂商 DMA 分配器把同一个 fd 同时交给 GstDmaBufMemory 和附属 qdata 释放。One-KVM 使用私有兼容分配器，fd 只由标准 GStreamer memory 关闭；需验证重复切换与缓冲区持有周期 | One-KVM/deploy/vim4/test-dma-allocator.c、tools/one-kvm-settings-check.mjs |
| 厂商 JPEG 插件直接输入 DMA 后只出 4 帧 | JPEG NEW_CMD 的直接 DMA 路径未释放导入，耗尽 VDIN 的 4 个采集缓冲。vim4jpegenc 使用 CONFIG_DMA_INPUT / RELEASE_DMA_INPUT 管理每帧生命周期，异常时先关闭编码器再归还输入；验证连续帧和重复启停 | gst-plugin-venc/tests/jpeg-hardware.py、logs/mjpeg-hardware/ |
| 编码器超频后帧率提升，就以为可用 | 750/800 MHz 下同一输入的码流已不再一致，但不报错、帧数正常。超频必须重复编码同一段录制输入并比较码流哈希，同时用低频对照排除时钟源问题 | [编码实验记录](../bringup/2026-10-14-wave521-clock-encode-time.md#wave521-时钟与-4k-编码耗时2026-10-14) |
| HDMI 输入稳定，编码器却不断重建 | sysfs 的 centi-Hz 测量可在 5987–5999 间抖动，原 0.1Hz 容差仍会误重启。改为超过 1Hz 且连续两次稳定读数才重建，并保留无帧看门狗；MJPEG 测试必须匹配真实输入尺寸，不能把离线占位图判为成功 | ustreamer/src/ustreamer/vim4.c、tools/pikvm-smoke.mjs |
| 网页走有线、WebRTC 报告 IPv4，却仍周期停顿 | Janus aggressive nomination 实测将视频发往客户端 Wi-Fi IPv6，selected candidate pair 统计不足以证明媒体路径。按 SSRC 对照两端网卡收发时间，使用 regular nomination；不通过关掉所有 IPv6 或一味缩短 GOP 掩盖路径问题 | kvmd/deploy/vim4/janus.jcfg、logs/pikvm/h264-client-wire.log、logs/pikvm/h264-regular-soak.log |
| PiKVM 短测 60fps，隔夜降到约 30fps 并卡顿 | 现场 JPEG 线程与网卡/JPEG IRQ 同在 CPU0；不重启做亲和性对照才能保留证据。uStreamer 避开 CPU0 后恢复 60fps；仍须同时检查浏览器 freeze 与 UDP 发送错误，平均帧率恢复不等于所有停顿消失 | kvmd/deploy/vim4/main.yaml、logs/pikvm/overnight/、tools/pikvm-smoke.mjs |
| Direct H.264/H.265 平均 60fps，却每个关键帧都停顿 | aiohttp 默认 permessage-deflate 对已压缩视频再次压缩，大关键帧拖慢发送。对照 memsink、无压缩/有压缩 WebSocket 的帧间隔后，仅禁用媒体 WebSocket 压缩；平均帧率与零 freeze 不能替代尾部间隔测量 | kvmd/kvmd/apps/media/server.py、kvmd/deploy/vim4/test_video_stream.py、logs/pikvm/cadence-* |
| One-KVM WebRTC H.264 每秒短顿，H.265 较顺，统计仍是 60fps/零 freeze | H.264 的一秒 GOP 产生大 IDR，编码和发送峰值使浏览器先停后追。VIM4 两种编码均逐行刷新，保留新订阅与 PLI/FIR 的完整关键帧；验证间隔尾部和恢复能力，不能只延长 GOP 或看平均帧率 | tools/one-kvm-smoke.mjs、[上板记录](../bringup/2026-10-18-onekvm-h264-periodic-stutter.md) |
| PiKVM HDMI 声音约每 1.37 秒啪一声，网络零丢包，arecord 录音正常 | 采集未设置周期/缓冲，TDM 驱动默认 241 帧周期配 65536 帧缓冲，每次回绕前 16 帧是上一圈旧数据。ALSA 采集显式设置与编码帧对齐的周期和有限缓冲；用应用实际协商的参数复现，arecord 的默认参数不同，不能代表应用路径 | ustreamer/janus/src/acap.c、[上板记录](../bringup/2026-10-16-pikvm-hdmi-audio-pops.md) |
| HDMI 重采样仍每圈跳变，客户缓冲明明是五周期 | ALSA rate 可给原生环增加插值帧，96kHz 实际为 9602/1920。核对原生 hw_params，T7 约束整数周期；应用原生采集后另做重采样 | [动态 LPCM](../bringup/2026-10-22-edge-hdmi-audio.md) |
| 原生HDR初次60fps，源端往返后编码器CMA失败或GPU回落CPU | 主采集池、VDIN1、GPU与编码器共用连续内存；先保留编码器200MiB，约束各池并完整释放旧管线。必须测真实PQ/SDR双向切换及期间截图；首次打开成功不能代表可重复 | [全局HDR与源端切换](../bringup/2026-10-26-hdr-global.md) |
