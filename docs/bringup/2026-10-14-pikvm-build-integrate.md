# 2026-10-14：PiKVM VIM4 构建、集成和上板验证

kvmd `638d12e0`、uStreamer `60fe8b1`、管理器 `ec46f9c`，主仓库配方
`e1b6967` 从干净源码构建 `2.5.1+vim4.20261014.34`。仅升级 vim4-pikvm 与
vim4-manager，其他板级和编码包保持 `.24`，内核 `5.15.137-vim4kvm`。
Janus 1.4.2 固定上游提交和 PiKVM JS 补丁，无额外 Janus fork。

ARM64 package、隔离 verify、board.py deploy 通过；验证包括真实 Janus WebSocket
会话及插件 attach/destroy、动态依赖、配置和认证文件升级保留。主机工具 44 项、
管理器助手 15 项、介质助手 3 项、管理器 Go 测试通过。kvmd 上游测试在 ARM64
私有 Python 3.14 中 743 项通过、3 个警告；测试使用上游配置和测试专用 PAM 依赖。
uStreamer 默认与 WITH_VIM4 编译均通过。实现提交尚未推送。

实机是 VIM4 HDMI 输入连接 macOS，浏览器为本机 Chrome，局域网访问 8080。
`.34` 完整测试初始 10 秒收到 585 帧，3840×2160；该次浏览器累计丢弃 19 帧，
WebRTC 报告 packetsLost=0。该数值是此测试窗口结果，不是持续运动性能或延迟保证。
独立彩色动态信源测试取得 8 个不同解码图像哈希；播放 440Hz WAV，浏览器收到的
HDMI 音频峰值 0.1546。JPEG 快照、3840×2160 MJPEG 与 WebRTC 来回切换通过。
鼠标实际位置和 Shift 修饰键状态通过；ISO 上传后 macOS 读到预期标记，主机 eject、
PiKVM 状态同步和镜像删除通过。切换到 30fps/8000kbps/质量70并刷新后继续出帧，
最后恢复原参数。挂载 ISO 时管理器拒绝切换，应用和介质仍保持原状。

修复三项实机问题：VFM 无 duration 的帧需显式 videorate 输出 caps；HDMI centi-Hz
读数 5998/5999 抖动不能每次都重建编码器；普通用户登录会话结束后的 IPC 清理会
使正在运行的 memsink 名称消失，服务整组改用私有 /dev/shm。虚拟介质 host eject
不触发厂商内核 configfs inotify，复用现有轮询核对 LUN file；unmount 不能代替 eject。

测试结束恢复 NanoKVM active/enabled，PiKVM disabled；原 512MiB disk.img 挂载恢复，
macOS 再次识别 NanoKVM 磁盘，USB 麦克风和网卡均为关闭，与测试前一致。
PiKVM 可在管理面板选择；先在 USB 主机安全弹出当前虚拟盘。ATX 未接硬件、H.265、
USB 麦克风、NBD 直连和树莓派固件更新不属于当前集成能力；未验证长时间稳定性、
WAN/NAT、端到端延迟、断电恢复或 PiKVM 可刷入整机镜像。

证据：`build/pikvm-package-34.log`、`build/pikvm-verify-34.log`、
`logs/pikvm/deploy-34/`、`logs/pikvm/final-smoke-34.log`、
`logs/pikvm/switch-guard-34.log`、`logs/pikvm/restored-state.txt`。
