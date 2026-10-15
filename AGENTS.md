# 任务路由

| 开始什么工作 | 先读什么 |
|---|---|
| 任何任务 | [工作区](docs/workspace.md)、[错题本](LESSONS.md) |
| 找脚本、测试入口及其对板子的影响 | [工具目录](docs/tools.md) |
| 写代码、审代码、提交 | [代码与协作规范](docs/code-standards.md) |
| 内核、驱动、设备树、风扇 | [内核](docs/subsystems/kernel.md) |
| 采集、编码、音频、WebRTC、测性能 | [音视频](docs/subsystems/video.md) |
| 键鼠、虚拟介质、USB-C 协商 | [USB](docs/subsystems/usb.md) |
| KVM 应用（NanoKVM、JetKVM、One-KVM、PiKVM）、管理面板、UU 远程 | [应用](docs/subsystems/application.md) |
| 构建、部署、串口、刷机、系统镜像 | [部署](docs/subsystems/deployment.md) |
| 板子账户密码、SSH/串口登录 | [默认账户](docs/hardware.md#默认账户开发环境) |
| 查历史测试证据 | [上板记录](docs/bringup-log.md) |
| 初始化仓库与构建 | [工作区初始化](docs/workspace.md#初始化入口) |
| 改完主仓库、提交前 | `python3 -m unittest discover -s tests -p 'test_*.py'`（离线，含文档链接与工具目录检查） |
