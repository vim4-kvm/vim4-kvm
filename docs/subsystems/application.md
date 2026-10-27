# NanoKVM 应用

三套 VIM4 应用的自定义 H.264/H.265 码率范围统一为 1000–60000 kbps。
NanoKVM 默认 12000 kbps、JetKVM 原质量档 12/6/1.2 Mbps、One-KVM 快捷档
1/4/8/12 Mbps 保留。JetKVM 通过 custom_bitrate 能力显示自定义输入。
部署这些版本时须同时升级 vim4-amlvenc（旧插件上限 12000 kbps），不能只更新网页。
高码率测试依据和局限见 [高码率实验](../encoder-high-bitrate.md)。

改 NanoKVM 读 [NanoKVM VIM4 集成](../../NanoKVM/VIM4.md)（功能覆盖、构建、安装和限制）；
其他应用读下方对应的 VIM4.md，只读与任务相关的一份。

当前可用功能、缺项与实测边界见 [功能状态](../feature-status.md)。
当前基线的迁移范围与软件验证见 [NanoKVM 基线切换](../nanokvm-migration.md)；
切换前的功能差异评估见 [NanoKVM 功能差异](../nanokvm-feature-review.md)，One-KVM 复核见 [One-KVM 审查](../one-kvm-audit.md)。

JetKVM 的功能映射、特权助手和验证见 [JetKVM VIM4 集成](../../kvm/VIM4.md)。

One-KVM 的硬件映射、构建和限制见 [One-KVM VIM4 集成](../../One-KVM/VIM4.md)。

四套应用都监听 127.0.0.1:8081，由管理器 8080 网关统一登录，以 khadas 运行，
互相 Conflicts=，不能并发占用编码器或 HID。由 vim4-manager（80 端口）选择开机启用哪一个，
部署时保留当前选择。板级服务拥有 HDMI、gadget、PD 和编码器时钟。
应用更新不能替代平台依赖。独立编码测试以相同用户共享 /tmp 锁空间，
不能删除活跃的 /tmp/vpu_mutex.map。

完整双内核运行时使用同一套 80 管理器 / 8080 网关和应用回环 8081。
`vim4-kvm-run` 按内核选择厂商或 V4L2/Wave5 后端，保留每种应用原有数据目录。
One-KVM 正式入口共用 `/var/lib/one-kvm`，板载设备名在内存中解析；
不合并四套应用的不同数据库。切换与数据验证见
[双内核集成](../bringup/2026-10-21-dual-kernel-integration.md)。

保留的 7.3 独立实验入口使用回环 8082，可通过
[实验登录网关](../bringup/2026-10-20-edge-lan-gateway.md) 在局域网 8080 访问，
沿用管理面板账户；该网关只随实验服务启动。

VIM4 后端使用 -tags vim4，保留上游目标实现。共享代码修改检查两个构建目标；
前端按锁文件构建，具体命令以 VIM4.md 为准。
网页登录由管理器负责；网络、更新沿用原 UI/API，经平台适配实现 Ubuntu 行为；
不能将上游整机固件更新部署到 VIM4。缺失外接硬件保持未配置。

One-KVM 的视频菜单和设置页支持 HDMI 输入状态、输出尺寸/帧率上限、码率、
MJPEG 质量和 EDID 预设；HDR 转 SDR 开关及白点/峰值曲线统一在管理器「视频输入」设置。
5.15 原生双路径的四套应用均支持 H.265 PQ/Main10，见
[全应用 HDR 接入](../bringup/2026-10-26-all-kvm-hdr.md)；H.264/JPEG 保留 SDR，
Safari 真 HDR 尚未支持。
四套应用的 HDR 缩放统一使用 Mali/P010 DMA；One-KVM 的 SDR 缩放通常使用 GE2D。
JetKVM、PiKVM 已新增输出高度入口；超宽屏 SDR 使用独立处理可见宽度和行跨度的公共 GE2D 缩放。
尺寸入口与实测边界见[超宽屏 SDR 与尺寸选择](../bringup/2026-10-27-sdr-scale-controls.md)。
调整输出尺寸不重启 HDMI 服务；
修改 EDID 才重新协商显示器。其私有 DMA 分配器避免厂商库重复关闭 fd，
随 vim4-onekvm 包安装；服务使用独立 GStreamer 注册缓存。参数与边界见
[One-KVM/VIM4.md](../../One-KVM/VIM4.md)。

One-KVM 的 UU 远程让网易UU远程官方客户端经云端控制被控机：网页扫码绑定账号，凭据存于
数据目录私有文件，共享 H.264/H.265 编码与 HID。网页可选择自动或固定编码，自动模式按
客户端及其他共享服务的能力回退。官方「终端远控」可打开 KVM 板子 shell、被控机串口（USB 转串口或占 2 个端点的 USB ACM gadget）与经板子的 SSH，三项默认关闭，新会话在终端内选择目标。范围与验证限制见 One-KVM/VIM4.md 的 UU 远程一节。
工具连接可在保留终端的同时取得桌面，统一管理 HID 接管。UU「文件传输」只暴露板子
`/files` 与未挂载的 `/images`，不能读取被控机磁盘；上传与所有虚拟介质挂载入口互斥。
协议、限制及验收见[UU 板子文件传输](../bringup/2026-10-25-uu-files.md)。
原生 UU 的独立十位解码声明、HDR 开关和非对齐缩放停帧修复见
[UU HDR 验证](../bringup/2026-10-27-uu-hdr.md)；MacBook持续显示与屏幕光度单独验收。

One-KVM 的「第三方接入」提供共享编码 SRT 与 RTMP/RTMPS 输出，默认关闭。
SRT 支持 H.264/H.265，RTMP 使用 H.264；可共享 HDMI 声音并转换为 AAC。
独立队列、断线重连和接收方式见 One-KVM/VIM4.md 的「共享编码 SRT / RTMP 输出」。

One-KVM 的外部 MCP（设置「扩展 → MCP」）让 Claude Code、Codex 等客户端经 `/api/mcp` 截图并操作键鼠，
工具沿用 computer use 命名与截图像素坐标，手动键鼠随时接管并冷却 2 秒。鉴权、截图管线、输入法与自然滚动限制见
One-KVM/VIM4.md 的 MCP 一节。被控机就是开发用 Mac mini 时，键鼠实测前须让用户停手并限定在测试窗口内。

## PiKVM VIM4 集成

PiKVM 源码在 `kvmd/`，VIM4 视频后端在 `ustreamer/`，部署约定见 `kvmd/VIM4.md`。
管理器选择 `pikvm` 启动 vim4-pikvm.service，应用监听 127.0.0.1:8081，由管理器 8080 网关统一登录。
它保留原生 PiKVM 网页，关闭应用认证，复用公共 HDMI、HID 和编码组件；本地虚拟介质使用
限定助手控制现有 LUN。切换前先安全弹出虚拟盘。构建使用 ubuntu-build.py 的
`--component pikvm`，不会替换系统 Python 或启动树莓派板级服务。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 沿用上游设备固件代码，在 Ubuntu 上以 khadas 运行时功能静默失败 | 设备固件默认 root 与自带工具（写 /proc/sys、tailscale set --login-server、reboot）。逐条走一遍特权路径，改经 sudo 助手；只有单元测试不足以发现 | kvm/VIM4.md、tools/jetkvm-smoke.mjs |
| 两个 KVM 共用后端 8081，切换后绑定失败或仍显示旧界面 | systemd Conflicts 不保证旧进程退出后才启动新进程。助手先等待 stop 完成再启动，失败时不启动替代程序；管理器链接区分应用，NanoKVM 首页禁用缓存 | vim4-manager/deploy/test_helper.py、tools/kvm-switch-check.mjs |
| PiKVM 原有视频能播放，但重新连接找不到共享内存 | 普通用户服务不能依赖登录会话的 IPC 生命周期。整组服务使用私有 /dev/shm，验证音频启停与 MJPEG/WebRTC 重连 | kvmd/deploy/vim4/vim4-pikvm.service、logs/pikvm/full-smoke-rate.log |
| 给 pion SettingEngine.SetNet 包装 UDP 套接字后进程空闲占满 3 核 | mDNS 的 ipv4.PacketConn 需要具体的 *net.UDPConn，包装后读取持续出错且非 ErrClosed，读循环空转。只包装单播套接字，部署前查空闲 CPU 与 pprof | NanoKVM service/stream/webrtc/batch_vim4.go |
| UU 客户端 H.265 一直"正在传输画面"，发送端 60fps 且零丢包 | libstreamer 的 H265VpsSpsPpsTracker 解析 AP 时从 data()+1 起按 2 字节 NAL 头遍历，错把第二个头字节当长度高位，AP 一律 kDrop；帧里缺 SPS/PPS，SpsPpsIdrIsH265Keyframe 把 IRAP 降级为 delta，解码器永不启动。VPS/SPS/PPS 必须拆成独立单 NAL 包发送，不能用 type 48 聚合包 | One-KVM/src/webrtc/h265_payloader.rs、/Applications/UURemote.app libstreamer.dylib 反汇编 |
| 管理器测试 NAS 连接总是笼统失败、中文共享名 error(2) | 测试挂载带 nofail 时 mount 返回 0，错误被吞；内核 NLS 默认 iso8859-1。测试挂载不带 nofail/_netdev，SMB 加 iocharset=utf8；单元改参数后需在升级时重新生成（storage-migrate） | [NAS 存储与 U 盘](../bringup/2026-10-18-nas-storage-usb-disk.md) |
