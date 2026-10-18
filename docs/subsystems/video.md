# 音视频

视频链路：HDMI RX port 1 → vdin0 → VFM tvpath → vfm_cap DMA-buf →
vfmcapsrc → amlvenc → NanoKVM WebRTC。板级 HDMI 服务打开输入并配置采集，
应用负责推流。video71 是输出回写。

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
若需要自动恢复，先分辨 HDMI 信号锁定、采集帧推进和浏览器解码各自的状态，
优先恢复故障环节；不能根据像素不变自动热插拔。

验收时分别记录 HDMI 服务运行实例、EDID/HPD 变更日志、输入锁定和浏览器解码状态：
覆盖无观看者、连续刷新、重新连接、应用重启和主机休眠恢复。
使用物理 HDMI 桌面上的运动标记验证内容更新，不能用虚拟桌面上的标记代替。
虚拟显示器退出后的恢复还需单独复测；切换 EDID 后恢复只说明重新协商有效，
不能据此确定故障在主机还是 VIM4。上述内容是行为约束，不代表所有场景已通过硬件验收。

## HDR 输入

内核在 vdin0 用 HDR2 核把 HDR10/HLG 输入映射到 SDR，SDR 直通；曲线由 `vim4-hdr-curve`
生成，参数在 `/etc/default/vim4-kvm-hdr`，管理器可实时调节。改 HDR 映射或曲线时读 [HDR 输入映射](../hdr.md)。

HDMI 启动脚本默认使用完整帧低延迟模式（VDIN mask 0x3）；
HDMI_LOW_LATENCY=0 恢复厂商自动策略。模式含义、对照结果及帧一致性检查见 [测量文档](../latency.md#board-side-isolation-and-completed-frame-mode)。

按改动范围读取（只读与任务相关的一项）：

- [采集插件](../../gst-plugin-vfmcap/README.md)：格式和 DMA-buf 生命周期。
- [编码插件](../../gst-plugin-venc/VIM4.md)：帧率预算、安装和测试。
- [应用与音频](../../NanoKVM/VIM4.md)：功能覆盖和构建。
- [视频配置](../../NanoKVM/deploy/vim4/VIDEO.md)：RTP、码率、GOP。
- [端到端测量](../latency.md)：软件端点定义和观测开销。
- [KVM 播放延迟复核](../kvm-playout-review.md)：各应用同步组、队列与媒体时钟风险及验证边界。
- [KVM 延迟差异调查](../kvm-delay-causes.md)：播放策略对照、接收耗时拆分、GOP 与时间戳差异。
- [编码实验记录](../encoder-experiments.md)：旧插件降级、帧率重建、QP 与行刷新验证。
- [HDMI 恢复路径对照](../hdmi-recovery-review.md)、[UU 虚拟屏恢复](../hdmi-uu-recovery.md)：显示器恢复故障的源码审查与现场取证。

编码器测试不能与应用或其他任务并发占用硬件。
验证区分静止/运动、分辨率/帧率切换、热插拔、重连和丢包恢复。
记录版本、配置、负载；帧率、吞吐量和端到端延迟分别报告。

## 4:4:4 采集

`HDMI_CAPTURE_FORMAT=YUV444` 是共享 HDMI 服务的可选格式，原始采集与 CPU 重排可达
4K60，但现有硬件编码只输出 4:2:0，应用仍用 NV21。改采集格式、vfm_cap 映射或
真彩编码前读 [4:4:4 采集](../capture444.md)。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 原始 DMA 采集 60fps，但全帧 CPU 处理只有约 13fps | write-combine 映射下读一帧 4K 需约 55.6ms，SIMD 无法弥补。改为只读可缓存映射并实现 DMA-BUF CPU 访问同步，融合复制与重排，复用输出缓冲；必须逐帧验证动态标记与单像素色度，不能只测重复读取同一帧 | common_drivers/drivers/media/vfm_cap/test_lifecycle.c、gst-plugin-vfmcap/tests/capture-integrity.c |
| 30fps 编码预算配 60fps 输入 | 旧 amlvenc 造成实际码率偏大。修正插件并传入输入帧率；预算不是采集节奏 | gst-plugin-venc/VIM4.md |
| 用 game_mode 0 当作关闭低延迟的实验对照 | 0 恢复自动策略，实际模式可能是 0xb。核对驱动 state 中的当前模式，不能仅看全局参数；完整帧模式使用 0x3 | [采集延迟对照](../latency.md#board-side-isolation-and-completed-frame-mode) |
| 把 video71 当 HDMI 输入 | vdin1 是输出回写；无 HDMI 输出时用 vdin0 → vfm_cap，HDMI RX 为 port 1 | [硬件](../hardware.md) |
| HDMI 有音频包、WebRTC 已连接但始终静音 | TDM-B 默认读外部引脚。HDMI 服务 ExecStartPre 在 ALSA restore 后选 hdmirx，再允许 NanoKVM 启动；零峰值录音不能证明声音正常 | [功能与音频状态](../feature-status.md)、packaging/ubuntu/check-audio-startup.py |
| GE2D 缩放单次成功，切编码后进程报 safe_close EBADF | 厂商 DMA 分配器把同一个 fd 同时交给 GstDmaBufMemory 和附属 qdata 释放。One-KVM 使用私有兼容分配器，fd 只由标准 GStreamer memory 关闭；需验证重复切换与缓冲区持有周期 | One-KVM/deploy/vim4/test-dma-allocator.c、tools/one-kvm-settings-check.mjs |
| 厂商 JPEG 插件直接输入 DMA 后只出 4 帧 | JPEG NEW_CMD 的直接 DMA 路径未释放导入，耗尽 VDIN 的 4 个采集缓冲。vim4jpegenc 使用 CONFIG_DMA_INPUT / RELEASE_DMA_INPUT 管理每帧生命周期，异常时先关闭编码器再归还输入；验证连续帧和重复启停 | gst-plugin-venc/tests/jpeg-hardware.py、logs/mjpeg-hardware/ |
| 编码器超频后帧率提升，就以为可用 | 750/800 MHz 下同一输入的码流已不再一致，但不报错、帧数正常。超频必须重复编码同一段录制输入并比较码流哈希，同时用低频对照排除时钟源问题 | [编码实验记录](../encoder-experiments.md#wave521-时钟与-4k-编码耗时2026-10-14) |
| HDMI 输入稳定，编码器却不断重建 | sysfs 的 centi-Hz 测量可在 5987–5999 间抖动，原 0.1Hz 容差仍会误重启。改为超过 1Hz 且连续两次稳定读数才重建，并保留无帧看门狗；MJPEG 测试必须匹配真实输入尺寸，不能把离线占位图判为成功 | ustreamer/src/ustreamer/vim4.c、tools/pikvm-smoke.mjs |
| 网页走有线、WebRTC 报告 IPv4，却仍周期停顿 | Janus aggressive nomination 实测将视频发往客户端 Wi-Fi IPv6，selected candidate pair 统计不足以证明媒体路径。按 SSRC 对照两端网卡收发时间，使用 regular nomination；不通过关掉所有 IPv6 或一味缩短 GOP 掩盖路径问题 | kvmd/deploy/vim4/janus.jcfg、logs/pikvm/h264-client-wire.log、logs/pikvm/h264-regular-soak.log |
| PiKVM 短测 60fps，隔夜降到约 30fps 并卡顿 | 现场 JPEG 线程与网卡/JPEG IRQ 同在 CPU0；不重启做亲和性对照才能保留证据。uStreamer 避开 CPU0 后恢复 60fps；仍须同时检查浏览器 freeze 与 UDP 发送错误，平均帧率恢复不等于所有停顿消失 | kvmd/deploy/vim4/main.yaml、logs/pikvm/overnight/、tools/pikvm-smoke.mjs |
| Direct H.264/H.265 平均 60fps，却每个关键帧都停顿 | aiohttp 默认 permessage-deflate 对已压缩视频再次压缩，大关键帧拖慢发送。对照 memsink、无压缩/有压缩 WebSocket 的帧间隔后，仅禁用媒体 WebSocket 压缩；平均帧率与零 freeze 不能替代尾部间隔测量 | kvmd/kvmd/apps/media/server.py、kvmd/deploy/vim4/test_video_stream.py、logs/pikvm/cadence-* |
| One-KVM WebRTC H.264 每秒短顿，H.265 较顺，统计仍是 60fps/零 freeze | H.264 的一秒 GOP 产生大 IDR，编码和发送峰值使浏览器先停后追。VIM4 两种编码均逐行刷新，保留新订阅与 PLI/FIR 的完整关键帧；验证间隔尾部和恢复能力，不能只延长 GOP 或看平均帧率 | tools/one-kvm-smoke.mjs、[上板记录](../bringup/2026-10-18-onekvm-h264-periodic-stutter.md) |
| PiKVM HDMI 声音约每 1.37 秒啪一声，网络零丢包，arecord 录音正常 | 采集未设置周期/缓冲，TDM 驱动默认 241 帧周期配 65536 帧缓冲，每次回绕前 16 帧是上一圈旧数据。ALSA 采集显式设置与编码帧对齐的周期和有限缓冲；用应用实际协商的参数复现，arecord 的默认参数不同，不能代表应用路径 | ustreamer/janus/src/acap.c、[上板记录](../bringup/2026-10-16-pikvm-hdmi-audio-pops.md) |
