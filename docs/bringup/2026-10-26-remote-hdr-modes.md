# 2026-10-26：远程 Main10 HDR、1440p120 与超宽屏

## 交付范围

5.15 原生双路径增加真正的远程 HDR10：VDIN0 原始十位样本转换为 P010，
由独立 HEVC Main10 编码器发送；VDIN1 继续提供 SDR H.264/H.265、JPEG 和截图。
One-KVM「HDR 转 SDR」默认开启，关闭后保留 PQ/BT.2020。HDMI OUT 偏好独立。
7.x、HLG、Dolby Vision 尚无这条远程 Main10 路径；不把十位编码名称当作 HDR 证明。

沿用现有 RTK UHD HDR，扩展到 384 字节，保留身份、首选 4K60、原 HDR/音频块，
加入 1440p120、2560×1080p60、3440×1440p60；不增加菜单预设。
NanoKVM、JetKVM 和 manager 共用新表，原始 256 字节 RTK 备份不变。
EDID SHA256 `ec7f330a18d36bed31f4de4ce104fa4e8844f1ef9d6dbdd89a2ab8f955792f92`。
驱动补齐 HDMI 专用尺寸/帧率枚举，保留回写口原有范围与枚举顺序。

## 修复与数据边界

- VDIN 的 AMLY 每 16 字节反序、十位 Y/Cr/Y/Cb 打包不能当作普通 P010。
  采集插件重排、垂直平均色度后输出 P010；NEON 与标量结果逐样本一致。
  Meson 显式使用 release，两个线程按行分工，完成后才归还 DMA；纯 4K 采集约 60fps。
- 扩展 SDK 与系统八位编码库 ABI 不同。插件用单个私有 linker namespace 加载匹配库，
  不替换系统库。SDK 修复 CPU P010 原地字节交换、非 32 对齐宽度只复制一半字节的问题。
  驱动尊重设备树 200MiB 编码池，不再覆盖成 100MiB，否则 UHD Main10 分配失败。
- 无 OUT 时只回收尚未被消费者获取的最新显示队列帧；已获取的帧与 DMA 引用仍须正常归还。
  `vfm_cap` 30 轮关闭/持有 DMA/STREAMOFF/REQBUFS0 生命周期通过。
- 厂商 GStreamer 的 PQ 枚举与构建机不同，颜色转换使用运行时 ISO API。
  RTP 的色彩扩展只放在每帧末包；浏览器同时核对解码帧的 PQ/BT.2020 与 SDP Main10。
- V4L2 采集协商使用源帧率，输出限帧放在后段。请求 15fps 输出不能把采集 caps 也设为 15，
  否则原驱动只枚举 24/25/30/50/60/100/120，会直接 not-negotiated。
- 运动标记揭示首版 QHD 画面损坏。旧 `parm.dest_width/height=3840×2160` 覆盖新几何，
  错误触发垂直缩放及 1920 行缓冲限制，实际 stride 与 V4L2 的 2560 不符。
  `9d33d52aa` 让共享 HDMI 采集使用当前 V4L2 输出尺寸；实际函数 C 回归 3 项通过。
  首版仅有约 120fps 的静态解码统计作废，不能当内容正确的证据。
- 3440×1440 另需区分可见宽度与行跨度：原 scaler 将3440向下取整为3392，
  但 V4L2 仍声明3440。原生采集保留3440，可缓存 DMA 行跨度向上补齐到3456；
  同步单/双平面的 bytesperline、sizeimage 与色度偏移。四项实际 C 函数回归通过。
- 原始 V4L2 帧正确后，八位编码插件仍默认以可见宽度作为 pitch，GE2D 缩放也忽略
  VideoMeta。编码器显式传 NV12/NV21 的实际 pitch；带填充的截图/缩放用标准 CPU
  转换。656×384、pitch704 的真实解码回归通过，H.264 / H.265 Y MAE=0.006 / 0.140。
  全帧先转换再缩放仅16.7fps；直接缩放NV21避免额外全帧转换，网页约35fps。

## UU HDR 生命周期

官方 Mac 客户端服务的 protobuf name map 确认 CaptureSettingRequest 字段 11 是
`enable_hdr`，HDR feature flag 是 6。CaptureSettingSync 字段 11 是屏幕方向，不能冒用。
本地 IDA 数据库与地址记录在忽略目录 `build/hdr-remote/uur-service.i64`。
样本 x86_64 slice SHA256：
`ed31060f0bf670a7172c4876193a3119e2ca99faca0fbc0a9f7816df20dcaf32`。

客户端提供 Main10 且硬件路径可用时协商 profile 2，声明 HDR 控制能力。
SDR 继续用高效的八位编码，其 SPS 同时声明符合 Main10；实际 HDR 才走 P010。
接收端按 SPS profile compatibility 检查，依据 [RFC 7798 §7.1](https://www.rfc-editor.org/rfc/rfc7798.html#section-7.1)。
不能向仅协商 Main 的接收端发送 Main10。

连接取得桌面时保存原 HDR 偏好，开关只改运行时、不写数据库；断开或被接管时恢复该偏好，
保留尺寸、帧率、码率。无信号也能恢复默认，不等待采集交帧。仅工具连接不修改 HDR。
首次 CONTROL 可能先于媒体任务到达：先选择协商编码，在修改期间持有视频订阅，
防止关闭网页会话时把共享管线当作空闲而停掉。

板端真实编码/本机 WebRTC 测试通过开→关→开、同一 peer 保持连接、Main10 兼容关键帧、
新客户端接管恢复默认、旧客户端退出不覆盖新设置、最后断开恢复默认。
这是协议与板端生命周期验收；官方 UU 客户端 HDR 菜单和实际显示效果仍待单独验证。

## 实测与限制

Mac mini HDMI → RX1，Chrome 经 LAN UDP 接收，HTTP 走本地 SSH 转发。
测试脚本仅将 mDNS candidate 替换为实测 Mac LAN IP，不改生产配置。

| 窗口 | 结果 |
|---|---|
| 真实 4K HDR 输入，SDR→HDR→SDR 网页 | BT.709 60fps → Main10/PQ/BT.2020 约34fps → BT.709 60fps |
| Main10 合成梯度，640/656/640×384 | 每轮30帧；十位解码与输入不变通过；Y PSNR约63–64dB，UV约58.8dB |
| 2560×1440p120 SDR，H.264 / H.265 | 119.68 / 119.62fps；各20个有效推进帧号，丢帧/冻结增量0 |
| 2560×1080p60 SDR，H.264 / H.265 | 59.95 / 60.01fps；各20个有效推进帧号，丢帧/冻结增量0 |
| 3440×1440p60 SDR，H.264 / H.265 | 59.92 / 59.91fps；各20个有效推进帧号，丢帧/冻结增量0 |
| 3440×1440缩到1720×720，H.264 / H.265 | 34.50 / 35.22fps；各20个有效推进帧号，丢帧/冻结增量0 |

4K HDR 的完整编码/网页链路尚未达到 60fps；纯采集 60fps 不代表完整链路。
缩放对照中一次命令误选厂商旧v4l2src，留下全局采集分频2；原始队列每帧跳一个
sequence、drop_divide增长，确认并恢复控制为1后复测。QHD约60fps及缩放约30fps的
受影响窗口不作最终性能结论；最终日志为mode-qhd-divider-final与scaled-ultra-divider-final。
没有 HDMI OUT 显示器，本轮不验收本地高刷、VRR、HDR 透传或显示器光度。
未运行长稳或 HDR VRR。没有新增音频测试。

## 版本、部署与回退

内核 release 仍为 `5.15.137-vim4kvm-hdrdual6`，保留 Image、DTB、启动项。
最终行宽/对齐修复模块 SHA256：
`8b300e74f40028c1f4459c3fb76299cfcab4888a06aeb4c56e3141232884a0f4`；
加载 note SHA256：`e013aee8a40997eb849002a857ceab9fedb60e6739c2ecd2d43ff51689debd3e`。
initrd SHA256：`23ec95261f7430b2ce4fab1293582978f96339ab4e53c4aaacafbfa20a2a2b07`。
One-KVM 二进制 SHA256：`7b7641c97266192dc5ddc3e5a355efd9bc9a650d8feaf6cd0d93ca469648628f`。
编码 SDK 固定 `d4ed7c0d088283da44470de157a3587d3addd2c0`，下载锁包含归档哈希；
组件包包含原始 SDK 归档、补丁和构建输入，保留原作者/许可证。

板端 `/var/backups/vim4-hdr-remote-20261026` 保存 runtime-before、kernel-before、
edid-before、数据库以及 before-enumeration/before-geometry/before-pitch 分阶段备份。
回退须恢复匹配模块、initrd、资格表、EDID 和用户态并 depmod；旧临时 restore-hdr.sh
仅恢复部分用户态，不能当作完整回退。JetKVM 二进制安装前未另存副本，须从旧提交重建。
启动仍存在既有 DRM vblank/时钟告警，不宣称无告警；未观察到本轮新增 Oops。

离线：One-KVM Rust lib 782 通过、3 忽略；网页 typecheck/build 通过；采集插件 3 通过；
RX/枚举 C 回归通过；manager 213 通过/12 跳过，Nano 助手43/8，Jet 助手19/3，
Jet Linux ARM64 Go 测试与构建通过。上游非 VIM4 检查受构建器 FFmpeg 缺
`AV_HWDEVICE_TYPE_RKMPP` 阻塞，不记为通过。日志与制品在忽略目录 `build/hdr-remote/`。
主仓库离线检查运行275项，7项跳过，包含新增记录的链接与体积检查。
未构建整机镜像，不能把组件构建/上板等同于镜像验收。

结束时保留候选运行：Mac恢复物理3840×2160p60、逻辑1920×1080、HDR关闭；
One-KVM恢复H.264、原尺寸、自动帧率（fps=0）、HDR转SDR开启，质量设置保持原值。
RX锁定SDR，三个视频服务active、failed单元0；关闭本次测试源和模式保持程序。
当前代码均为本地提交，尚未推送；完整固定版本见workspace.toml，分享清单前须先推送子仓库。
