# 2026-10-15：部署 EDID 管理器，并保留 UU 虚拟屏故障现场

用户补充：真实 UU 客户端连接并创建虚拟屏后，即使使用 RTK UHD HDR 也无法恢复。
因此 RTK 的既有 Screen Sharing 成功记录不能推广到 UU 场景，管理器预设说明同步修正。
部署前 Mac system_profiler 仅显示名为 Display 的 1080p 输出，板端 fmt_valid=1、
sm_state=5。此记录尚不能确定虚拟屏创建者与恢复失败根因。

管理器 `.42` 使用本机 Go 交叉编译 ARM64、板上 dpkg-deb 组包，复用 package.py
的 manager 文件清单；未运行 Docker 隔离构建。经 board.py 的新 manager 单组件
路径安装，APT 仅升级 vim4-manager。安装前后 One-KVM、tvserver、HDMI 服务
InvocationID、加载 EDID 标记时间戳、active.bin SHA256 及采集状态完全一致。
无 EDID 重发、应用切换或采集重启。包和构建来源在 build/packages/2.5.1+vim4.20261015.42。

管理器 Python 25 项、Go 测试、前端构建、board tools 28 项与安装脚本语法检查通过。
安装后 GET /api/edid 返回三项预设、RTK-CONTROL 和 JetKVM 已同步状态。
证据：logs/manager-edid-deploy/（安装日志、部署前后状态、Mac 显示记录和网页截图）。
