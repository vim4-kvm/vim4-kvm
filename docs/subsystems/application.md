# NanoKVM 应用

三套 VIM4 应用的自定义 H.264/H.265 码率范围统一为 1000–60000 kbps。
NanoKVM 默认 12000 kbps、JetKVM 原质量档 12/6/1.2 Mbps、One-KVM 快捷档
1/4/8/12 Mbps 保留。JetKVM 通过 custom_bitrate 能力显示自定义输入。
部署这些版本时须同时升级 vim4-amlvenc（旧插件上限 12000 kbps），不能只更新网页。
高码率测试依据和局限见 [高码率实验](../encoder-high-bitrate.md)。

先读 [VIM4 集成](../../NanoKVM/VIM4.md)，其中维护功能覆盖、
构建、安装和限制；代码规范见 [code-standards.md](../code-standards.md)。

当前可用功能、缺项与实测边界见 [功能状态](../feature-status.md)。
当前基线的迁移范围与软件验证见 [NanoKVM 基线切换](../nanokvm-migration.md)。

JetKVM 的功能映射、特权助手和验证见 [JetKVM VIM4 集成](../../kvm/VIM4.md)。

One-KVM 的硬件映射、构建和限制见 [One-KVM VIM4 集成](../../One-KVM/VIM4.md)。

nanokvm.service、JetKVM 的 vim4-kvm.service 与 one-kvm.service 都监听 8080、以 khadas 运行，
互相 Conflicts=，不能并发占用编码器或 HID。由 vim4-manager（80 端口）选择开机启用哪一个，
部署时保留当前选择。板级服务拥有 HDMI、gadget、PD 和编码器时钟。
应用更新不能替代平台依赖。独立编码测试以相同用户共享 /tmp 锁空间，
不能删除活跃的 /tmp/vpu_mutex.map。

VIM4 后端使用 -tags vim4，保留上游目标实现。共享代码修改检查两个构建目标；
前端按锁文件构建，具体命令以 VIM4.md 为准。
账户、网络、更新沿用原 UI/API，经平台适配实现 Ubuntu 行为；
不能将上游整机固件更新部署到 VIM4。缺失外接硬件保持未配置。

One-KVM 的视频菜单和设置页支持 HDMI 输入状态、输出尺寸/帧率上限、码率、
MJPEG 质量、EDID 预设和共享 HDR 曲线。输出缩放使用 GE2D，不重启 HDMI 服务；
修改 EDID 才重新协商显示器。其私有 DMA 分配器避免厂商库重复关闭 fd，
随 vim4-onekvm 包安装；服务使用独立 GStreamer 注册缓存。参数与边界见
[One-KVM/VIM4.md](../../One-KVM/VIM4.md)。
