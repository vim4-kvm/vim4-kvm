# 2026-10-20：7.x 1080p60/4K60 自动切换与缓冲回收

RGB8 1080p60 ↔ 3840×2160p60 已接通 RX PHY、音频分频、VDIN 队列几何和
One-KVM 重建。网页连接保留，H.264/H.265 可恢复原生尺寸、截图和 HDMI 音频。
这是两个受支持输入模式的实验适配，其他帧率、YUV、深色及 HDR 尚未接入。
5.15 默认启动项、Image、应用、数据库和插件保持原样。

## 源码与部署

Linux `f30d0edc36c9ba0ef3719b81e7770a3dcf95e5c3`，tree
`3878448de7f2a12f459abe051f8700eb52cb5993`。完整 2333 个 BTF 模块与原 Image
匹配，包 SHA256 `742e5a2835da164696c2e474399842a9e059146b4597c2e254a9c24b326ee9bf`；
Image 仍为 `fc9d524a9f7bd06fd89e98f97effc0e44a3eb05f48ebed4a343ffb906a8b2b33`，
build ID `cd0b47762bd10b4c02dbf43b369b57ab182d1fb5`，实验 DTB 不变。
加载的 RX/VDIN build ID 分别为 `a1054573d7a9796e420effe3d7f46cf7aa42e4a6` /
`76e5eb0cd9b42684bc91aa106fc63f36b3c304c4`。

One-KVM `97e810005ea6f8dde6a66a918dc44c7d323dbdc6`，ELF SHA256
`f804b8d06cbfe9b1c0d96f90421c2d95485d402ff452e2183a029e276a545af9`。
私有 GStreamer 插件 SHA256
`5302d0fa8c6f1089173634206815f6a9709782263a343915e24b95b5e9eddaca`。
备份在 `/var/backups/vim4-onekvm-edge-20261020/dynamic-{modes,app}/`、
`dynamic-buffer-app-verified/`、`dynamic-orphan-plugin/`。

RX 新增只读 opt-in `dynamic_modes=1`，默认固定模式不变。按稳定的 cable meter 与
SCDC ratio 区分两个模式，持有采集租约时不改 PHY。运行时只改模拟部分，不覆盖
首次保存的 TOP 状态，不操作 EDID/HPD。ALSA 与模式变化共用音频锁，切模式时调整
CTS 分频；同模式重新锁定不重置音频。

VDIN 按最大 UHD 容量保留私有缓冲，当前队列布局独立管理。TRY_FMT 查询新输入，
G_FMT 返回已应用布局；S_FMT 要求旧 vb2 缓冲已释放，STREAMON 再核对 RX 几何，
避免旧尺寸写入新流。1080p 的导出分配含编码器 1088 行尾部容量，UV 仍紧接有效 Y。
250ms 工作项发布标准 SOURCE_CHANGE；One-KVM 的输入状态不再受旧 G_FMT 尺寸限制，
原有源监控重建采集和编码，订阅者与 SSRC 保留。

## 缓冲回收故障与修复

最初两种编码都能出画面，但空闲后残留 12 个 DMA-buf、约 98MiB。关闭桥接和
压缩帧 appsink 的 last-sample 缓存后，仍可残留一组 1080p 分配，不能把该改动
单独记为泄漏修复。leaks tracer 显示池和视频 fd 已释放，旧 V4L2 allocator 及
GstMemory 仍在；详细逐帧日志下连续通过，正常日志级别又复现。

GStreamer 1.24.2 的 orphan 先调用 set_active(false)，其中 stop() 未持有 QBUF
锁。STREAMOFF 冲刷后、orphan 标志置位前，编码器归还的缓冲仍能 QBUF；后续
streamoff 因 streaming=false 不再冲刷，留下排队内存引用。新增
[orphan 顺序补丁](../../packaging/kernel-edge/gstreamer-v4l2-orphan-order.patch)：
先停止获取，在 QBUF 锁内停流并完成 orphan，再停用池。

[离线夹具](../../packaging/kernel-edge/test_gstreamer_orphan.py) 提取真实 orphan / QBUF
函数，在停用回调中确定性归还采集租约。旧函数在引用归零断言失败，新函数通过；
还检查空池、不支持 orphan、强制 drain、已 orphan 和失败请求的池所有权。
它模拟内核队列边界，不替代真实 DMA 并发测试。可在 Linux 执行：

```sh
python3 packaging/kernel-edge/test_gstreamer_orphan.py /path/to/sys/v4l2/gstv4l2bufferpool.c
```

私有插件按 [源码锁](../../packaging/kernel-edge/sources.toml) 的官方 1.24.2 归档和
四个补丁顺序重建，沿用 [Meson 命令](2026-10-19-wave521-uhd.md#固件与复现依赖)。
不替换系统或生产插件。

部署一次误取了 Mac 上旧 target 目录的 ELF，启动参数校验失败后回滚。最终产物
由构建容器的 target 卷复制并校验，增加 --help 参数预检；旧版服务随后恢复正常。
这次失败与回滚日志保留，不计入通过。

## 硬件验证与边界

Chrome 固定 `156.0.8078.47`，LAN 网关 `192.168.50.210:8080`，原生 HDMI 桌面运动
网格、三处帧号和 RGB 色块。输入状态、浏览器实际解码尺寸与新鲜 JPEG 尺寸分别核对；
每个模式播放 HDMI-only 440Hz 测试音并在网页解码端检查非零峰值。

Mac 的普通“1080p”模式仍发 4K 信号，另一个枚举的物理 FHD 模式设置被系统拒绝。
因此本轮用显式、可恢复的临时 EDID RAM 夹具诱发真实线缆模式变化：FHD 只保留已有
VIC16/LPCM，原始 EDID 恢复 UHD 首选与 VIC16。固件和驱动缓存不改，结束后逐字节
核对恢复。它是测试信源夹具，不是已交付的 EDID 配置 API；普通网页连接不改 HPD。

每次切换经 V4L2 查询确认 1920×1080 / 3840×2160、约 59.999Hz；原 SSRC 上继续
解码，截图同尺寸，音频恢复。SOURCE_CHANGE 覆盖失锁和恢复。采样中的 recoveredMs
含信源切换、帧资格检查和截图，不能作为纯切换时间或端到端延迟。

最终关闭逐帧日志和 tracer，两种编码各完成五轮往返（各十次切换），全程各保留
一个 SSRC。每个目标模式有五次独立 5 秒采样：

| 编码 / 输入 | 解码 fps 范围 | 网页音频峰值下限 | JPEG 字节范围 |
|---|---:|---:|---:|
| H.264 / 1080p60 | 59.952–59.978 | 0.1017 | 187607–218975 |
| H.264 / 4K60 | 59.767–59.976 | 0.1015 | 505948–522615 |
| H.265 / 1080p60 | 59.957–60.154 | 0.1015 | 199964–249806 |
| H.265 / 4K60 | 59.953–59.972 | 0.1020 | 509154–626470 |

五秒统计窗口边界可略高于 60；这些是解码吞吐量，不是均匀呈现或光学延迟证明。
最终二十个采样都在第一个窗口通过，未使用后备窗口。两种编码各收到二十个
SOURCE_CHANGE（失锁/恢复），二十张 JPEG 的三处帧号均校验有效且一致，同编码
各次快照帧号不同，证明真实 HDMI 内容推进且这些采样未撕裂，不代表逐帧完整检查。
两轮退出后 DMA-buf 都严格归零，最终 CmaFree 505192KiB，与本构建先前空闲基线相同；
VDIN fault=0、dma_idle=1、内核 taint=0。音频启用且无订阅、错误为空，服务正常。

一次连续 H.264 检查的首个恢复采样窗口约 42fps，该轮不记为稳定播放通过。后续
夹具明确记录最多三个 5 秒窗口，要求恢复至 55–65fps 且尺寸正确；所有窗口保留，
不降低阈值。另一轮完成十次模式变化，但 Mac CoreText 使运动源异常退出，测试
清理也曾等待已退出进程；该轮不记为完整运动场景通过。测试源增加 --no-labels
以保留网格/像素标记并跳过文字，清理明确检查进程退出状态。

## 离线检查

内核实际 C 的 core/DDC/PHY/link/audio/VDIN/stream/timings/ioctl_locks/source_events
十组通过；包含租约期间禁止改 PHY、旧尺寸拒绝、忙时格式拒绝、尾部容量和 source-change
边界。完整 Image/dtbs/modules 构建通过。One-KVM 722 项通过、2 ignored，ARM64
release 构建通过；新桥接测试检查已消费帧不进入 last-sample 缓存及停流后租约释放。
主仓库离线 124 项测试结束：119 通过、5 跳过。Mac 无文字运动源编译通过，最终两轮
运行期间未提前退出。恢复为 H.265、原 UHD EDID 与原 Mac 显示模式。

日志为 `logs/kernel-edge/edge-dynamic-*`，包括失败样本、离线红绿对照、源码构建、
部署、网页、事件、音频、运动源和截图。没有验证物理拔线、整机休眠、其他帧率、
HDR/YUV/深色、长期耐久或整机镜像发布。后续 HDR 按 [HDR 输入映射](../hdr.md)
对照 5.15 的 YUV420 10bit HDR10 输入、HDR2 映射及 SDR 白/高光曲线，不能仅声明 EDID。
