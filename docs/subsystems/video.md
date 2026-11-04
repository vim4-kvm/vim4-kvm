# 音视频

## HDMI 显示器行为

HDMI独立于浏览器，无观看者仍保留EDID和连接；HPD仅表示接收端存在，不保证输出，也不能强制主机退出休眠或虚拟显示器。

| 事件 | 行为 |
|---|---|
| 刷新、连接、断开网页，改编码、码率或缩放 | 只调整推流、采集或编码，不改EDID、不脉冲HPD、不重启HDMI |
| 相同 EDID 的应用重启 | 幂等恢复、保持连接 |
| 用户改 EDID/明确重连 | 可重新协商/热插拔，可能黑屏、重排显示器 |
| 源停止输出、休眠或切虚拟显示器 | 保留连接，区分无信号与采集故障，不周期重写 EDID |

用户主动隐藏显示器是JetKVM的例外；应用间EDID不同可重协商，网页连接不触发。
恢复时分别查HDMI锁定、采集推进和浏览器解码，不凭像素不变热插拔。
输入变化只重建采集和编码，保留WebRTC且跳过故障退避；VDIN1池须限额防CMA不足，见[HDR](../hdr.md#验证边界)。
验收记录服务实例、EDID和HPD日志、输入锁定及解码，覆盖无人观看、刷新、重连、应用重启，以及休眠和虚拟显示器退出后的恢复。
物理桌面运动标记须推进，帧率不证明内容更新；EDID切换恢复不能定位主机或VIM4故障，各场景尚未全验。

## HDR 输入

[HDR](../hdr.md)规定默认、双路径、部署顺序和边界；5.15远程HDR与7.x的HDR→SDR映射分别验收，见[原生门禁](../hdr10-remote-73.md)。

## 按改动范围读取

- [内核证据](../kernel-mainline.md#相关记录)。
- [延迟](../latency.md#相关记录)；[播放差异/未决项](../kvm-delay-causes.md)。
- [RTP](../archive/rtp-send-optimization-audit.md)、[编码库](../archive/encoder-fast-packing-audit.md)：后端、ABI及硬件边界。
- [高刷](../archive/1080p120-audit.md)、[VRR](../vrr-preparation.md)：输入/本地输出。
- [驱动](../driver-benchmark.md)、[本地视频](../local-video-benchmark.md)：按端点选工具。
- [采集插件](../../gst-plugin-vfmcap/README.md)：格式/DMA-buf；[编码插件](../../gst-plugin-venc/VIM4.md)：预算、安装与测试。
- [应用/音频](../../NanoKVM/VIM4.md)；[视频参数](../../NanoKVM/deploy/vim4/VIDEO.md)：RTP、码率及GOP。

完整帧低延迟、自动策略和帧一致性见下方错题。
编码器须[独占](application.md#架构与约束)；验证静止和运动、分辨率和帧率切换，以及热插拔、重连和丢包恢复，分别报告帧率、吞吐和端到端延迟，字段按[规范](../code-standards.md)。

## 4:4:4 采集

硬编不保留4:4:4；改采集格式、vfm_cap映射或真彩编码先读[4:4:4](../capture444.md)。

## Wave5 隔离告警

复位失败须保留DMA内存和映射至重启；自动重启须全部KVM停用且无介质，One-KVM空闲不代表无消费者。[接口、计时、部署与回退](../kernel-mainline.md#wave5-隔离告警)。

## 错题

| 触发条件 | 正确做法 | 验证入口 |
|---|---|---|
| vb2 前置元数据使回调代号错位 | vb2 保持首成员、加编译断言；独立 export 不凭 inode 关联，cleanup 不等于编码完成 | [HDR2](../hdr2-dma-contract.md) |
| 误读last_wr_vfe时序 | 匹配实际缓冲和pending/已执行表；地址提交、执行和交付分拍，寄存器DMA完成不等于图像写完 | [逐缓冲](../bringup/2026-10-25-vdin1-frame-handoff.md) |
| 7.x JPEG DMA 导入 reservation-lock WARN | map/unmap_attachment 用 unlocked helpers 管锁，不带 taint 继续验收 | [MJPEG](../bringup/2026-10-21-edge-scaling-jpeg.md) |
| 分辨率切换后无 fd 仍留 CMA | STREAMOFF 后归还仍可 QBUF、orphan 无流可冲刷；先停获取，QBUF 锁内停流/完成 orphan，再停池，关 last-sample 不够 | [动态模式](../bringup/2026-10-20-edge-dynamic-modes.md) |
| 无周期IDR仍短顿 | ENUMINPUT双稳检查持锁等待；实时读/清旧状态，STREAMON保留稳定检查，移查询线程仍争锁 | [实测](../bringup/2026-10-20-edge-status-latency.md) |
| 7.3 重配耗 CMA、失败 Oops | 补每帧池 unref/空 LAST 归还、DMA副本/实例重复释放；SET_FB 后保留 DMA 至固件停止，每轮查 fd/CMA，不只查退出后 | tools/wave5-lifecycle-check.py、[应用接入](../bringup/2026-10-20-onekvm-wave5.md) |
| Wave5导入720×400报EINVAL | VDIN行对齐须满足Wave5协商RAW stride；保留可见宽，两平面/UV按实际stride，查高度补齐容量 | [模式覆盖](../bringup/2026-10-22-edge-hdmi-modes.md) |
| 强制 IDR 仅首次有效 | 按编码标KEYFRAME，否则请求不完成；GOP长于测试，连续请求核输出 | [接入](../bringup/2026-10-20-onekvm-wave5.md) |
| DMA快、CPU全帧慢 | WC读慢，SIMD无济；只读cached映射+DMA-BUF CPU同步，融合复制/重排、复用输出；逐帧验动态标记/单像素色度，不重复读同帧 | gst-plugin-vfmcap/tests/capture-integrity.c |
| cached DMA 环遗漏首次设备同步 | dma_alloc_noncoherent 由 CPU 清零，首次 DMA 前也须 sync_for_device；每轮交接 CPU/设备所有权 | [私有环](../bringup/2026-10-19-hdmirx-dma-ring.md) |
| 30fps预算配60fps输入导致旧 amlvenc 超码率 | 修插件并传输入帧率，预算不等于采集节奏 | gst-plugin-venc/VIM4.md |
| game_mode 0 被当低延迟关闭 | 0是自动；查驱动state，不只看全局参数，完整帧模式按测量文档 | [模式对照](../latency.md#board-side-isolation-and-completed-frame-mode) |
| stock video71误作HDMI | 原厂vdin1是输出回写，原生HDR双路径显式共享主RX才是例外；普通走vdin0→vfm_cap | [双路径](../bringup/2026-10-25-native-hdr-dual-path.md) |
| 有音频包/WebRTC却静音 | ALSA restore后选HDMI输入再启应用；TDM-B外部引脚不是HDMI，零峰值不算正常 | packaging/ubuntu/check-audio-startup.py |
| GE2D切编码报EBADF | 同 fd 被 GstDmaBufMemory/qdata 双关；One-KVM 私有分配器仅由标准 memory 关，测重复切换/持有周期 | tools/one-kvm-settings-check.mjs |
| JPEG直接DMA仅出4帧 | NEW_CMD 不释放导入耗尽4缓冲；vim4jpegenc 每帧 CONFIG_DMA_INPUT/RELEASE_DMA_INPUT，异常先关编码器再归还输入 | gst-plugin-venc/tests/jpeg-hardware.py、logs/mjpeg-hardware/（连续帧/重复启停） |
| 超频增帧却码流无声损坏 | 重复编码同录制输入比哈希，低频对照排除时钟源，帧数正常不算通过 | [时钟实验](../bringup/2026-10-14-wave521-clock-encode-time.md#wave521-时钟与-4k-编码耗时2026-10-14) |
| 稳定HDMI仍重建编码器 | centi-Hz抖动误重启；按 ustreamer/src/ustreamer/vim4.c 的稳定性判据，保留无帧看门狗；MJPEG匹配真尺寸，不认占位图 | tools/pikvm-smoke.mjs |
| IPv4统计/有线网页仍周期顿 | Janus aggressive nomination 实际走Wi-Fi IPv6；按SSRC对照两端网卡收发，改 regular nomination，不靠禁IPv6/缩GOP掩盖 | kvmd/deploy/vim4/janus.jcfg、logs/pikvm/h264-regular-soak.log |
| PiKVM短测60、隔夜约30fps | JPEG线程、网卡和JPEG IRQ挤在CPU0；不重启做亲和对照保留证据，uStreamer避CPU0；同时查浏览器freeze/UDP错误，均帧恢复非全停顿消失 | logs/pikvm/overnight/、tools/pikvm-smoke.mjs |
| Direct视频均帧正常、关键帧顿 | aiohttp permessage-deflate 重压视频；比较memsink、压缩与无压缩WebSocket的帧间隔，仅禁媒体压缩，均帧/零freeze不替代尾间隔 | kvmd/deploy/vim4/test_video_stream.py、logs/pikvm/cadence-* |
| One-KVM AVC每秒顿、统计60fps | 大IDR致先停后追；恢复帧/渐降QP按[补丁](../../packaging/kernel/gstreamer-v4l2-avc-recovery-qp.patch)，验证订阅、PLI和FIR恢复 | [恢复帧](../bringup/2026-11-03-wave5-avc-recovery-qp.md) |
| PiKVM周期爆音，网络和arecord正常 | 周期/缓冲不整除产生回绕旧数据；显式设编码帧对齐周期/有限缓冲，按应用协商参数复现，arecord不代表应用 | [爆音](../bringup/2026-10-16-pikvm-hdmi-audio-pops.md) |
| 重采样环跳变，客户缓冲五周期 | ALSA rate插值破坏整周期；查原生 hw_params，T7限整数周期，应用原生采集后重采样 | [LPCM](../bringup/2026-10-22-edge-hdmi-audio.md) |
| HDR切换后CMA失败或GPU回落CPU | 池共享CMA，优先留编码器预算、限池/释放旧管线，测真实PQ↔SDR及期间截图，首开非可重复 | [源切换](../bringup/2026-10-26-hdr-global.md) |
| strace跟踪One-KVM使UU掉帧 | ptrace干扰多线程，过滤fd仍高开销；用程序内有界计数/低频汇总或独立接收窗口 | [滚轮](../archive/uu-scroll.md) |
| 像素回读时间误作网络延迟 | 4K回读/JS调度扰动，低频采样、分报回读成本，并行测量作废 | [测量](../latency.md) |
| 采样时编译致丢包/停解码 | 先构建后独占采样，重叠不归因播放策略；保留失败数据，查全窗口推进 | [对照](../kvm-delay-causes.md#pikvm-正式启用低缓冲策略与限制) |
