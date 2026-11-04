# KVM 应用与管理面板

管理器开发：[结构](../../vim4-manager/README.md#结构)、[构建验证](../../vim4-manager/README.md#构建与验证)、[i18n](../../vim4-manager/docs/i18n.md)。
应用的功能、构建、安装和限制只读对应集成：[NanoKVM](../../NanoKVM/VIM4.md)、[JetKVM](../../kvm/VIM4.md)、[One-KVM](../../One-KVM/VIM4.md)、[PiKVM](../../kvmd/VIM4.md)。

## 架构与约束

应用回环监听、共用管理器登录网关；服务入口/后端选择见[vim4-kvm-run](../../board/vim4-kvm-run)。
应用互斥，不能并发占编码器/HID，部署保留当前应用选择；HDMI、gadget、PD和编码时钟归板级服务。
独立编码测试须同用户、同/tmp锁空间，不删活跃锁；应用更新不能替代平台依赖。
升级自定义码率功能须同时升级编码插件，不能只更网页；范围/快捷档以各应用实现为准。

双内核共用管理器/网关，保留各应用数据目录，不合并数据库；One-KVM板载设备名仅在内存解析。
切换/旧实验见[内核记录](../kernel-mainline.md#相关记录)。
VIM4适配保留上游目标；共享代码检查两种构建，前端按锁文件，命令见对应集成。
网络/更新保留原UI/API，经平台适配Ubuntu，不部署上游整机固件；未接硬件保持未配置。
管理器与各应用语言独立，文案/新增语言按[i18n](../../vim4-manager/docs/i18n.md)。

One-KVM视频菜单和设置页的输入状态、尺寸、帧率、码率、MJPEG及EDID以集成为准。
HDR→SDR及白点/峰值统一在管理器视频输入；模式/内核验收见[HDR](../hdr.md)。
H.264/JPEG保留SDR，Safari真HDR未支持。HDR缩放走Mali/P010 DMA，One-KVM SDR通常GE2D；
超宽SDR分开处理可见宽/stride，[尺寸证据](../hdr.md#相关记录)。
EDID/显示器恢复合同统一见[音视频](video.md#hdmi-显示器行为)。
服务隔离GStreamer注册缓存；[DMA fd错题](video.md#错题)。

## One-KVM 外部接入

以下协议、选项和接收方法均见[One-KVM集成](../../One-KVM/VIM4.md)，这里只列边界：

- UU官方客户端经云控制被控机，网页扫码，凭据存数据目录私有文件，共享编码/HID；自动编码按客户端/共享服务能力回退。
- UU终端可进板shell、被控机串口或经板SSH，默认关闭，新会话在终端选目标；USB ACM占端点预算。
- 工具连接可保留终端同时取桌面，统一HID接管；文件传输仅板子文件区/未挂载镜像区，不能读被控盘，上传与所有虚拟介质挂载互斥。
- UU HDR见[证据](../hdr.md#相关记录)，持续显示/屏幕光度另验。
- 第三方SRT/RTMP输出默认关，共享编码/HDMI音频，队列独立并可重连；编码支持/AAC转换按集成。
- 外部MCP截图/键鼠沿用computer use命名、截图像素坐标，手动随时接管并冷却；鉴权、截图管线、输入法和滚动限制按集成。被控机是开发Mac时，实测须用户停手、限定窗口；本项目M4禁发HID见[规范](../code-standards.md)。
- transport失败后，先重新发送只读initialize、tools/list和screenshot请求，区分HTTP错误、无信号或进程网络差异，不直接判板端失败。
- LAN接收仅默认mDNS candidate失败时，用接收器显式选项A/B；不直接改个人VPN/TUN。[实证边界](../hdr.md#相关记录)。

## PiKVM VIM4 集成

源码/视频后端见[kvmd集成](../../kvmd/VIM4.md)；保留原生网页、关闭应用认证，由公共网关认证。
复用HDMI、HID和编码组件，虚拟介质由限定助手操作现有LUN，切换前安全弹出。
独立组件构建/部署见[部署](deployment.md)，不替换系统Python、不启动树莓派板级服务。

## 错题

| 触发 | 做法 | 验证 |
|---|---|---|
| 重启切HDR/UU切codec后仍有统计 | 先验4K framesDecoded推进；codec切换可关闭会话，后续冻结不算恢复时间，MCP逐屏确认 | [细采样](../bringup/2026-10-31-hdr2-recovery.md) |
| 上游固件在Ubuntu普通用户下静默失败 | 上游假设root/自带工具；逐条走写proc、tailscale、重启等特权路径，经sudo助手，单元不足 | tools/jetkvm-smoke.mjs |
| 切应用绑定失败/显示旧界面 | Conflicts不保证stop完成；助手先等停完再启，失败不启替代；管理器区分应用链接，Nano首页禁缓存 | tools/kvm-switch-check.mjs |
| PiKVM重连找不到共享内存 | 普通用户服务不依赖登录IPC生命周期，整组服务用私有共享内存，验音频启停/MJPEG及WebRTC重连 | kvmd/deploy/vim4/vim4-pikvm.service、logs/pikvm/full-smoke-rate.log |
| pion包装UDP后空闲占满CPU | mDNS需具体UDPConn，包装导致非ErrClosed读错空转；仅包单播，部署前查空闲CPU/pprof | NanoKVM service/stream/webrtc/batch_vim4.go |
| UU H.265发送正常、解码不启动 | libstreamer AP解析错位丢SPS/PPS、IRAP降delta；参数集拆独立单NAL，禁type48聚合 | One-KVM/src/webrtc/h265_payloader.rs、UURemote libstreamer.dylib反汇编 |
| NAS测试笼统失败/中文名error(2) | nofail吞失败、NLS缺UTF-8；测试不用nofail/_netdev，SMB设UTF-8；参数改后升级需storage-migrate重生成 | [NAS](../bringup/2026-10-18-nas-storage-usb-disk.md) |
