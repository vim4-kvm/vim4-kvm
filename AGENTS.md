# 任务路由

子系统文档和代码规范末尾的「错题」随路由生效。
不通读 docs/、docs/bringup/；长文先看摘要、目录，再选章节。

| 开始什么工作 | 先读什么 |
|---|---|
| 初始化仓库、构建、跨仓库改动 | [工作区](docs/workspace.md) |
| 脚本、测试入口及板端影响 | [工具目录](docs/tools.md) |
| 写代码、审代码、提交、上板测试 | [代码与协作规范](docs/code-standards.md) |
| 查已知问题、登记审查中的 file 类发现 | [issue 清单](docs/issues.md) |
| 内核、驱动、设备树、风扇 | [内核](docs/subsystems/kernel.md) |
| 采集、编码、音频、WebRTC、测性能 | [音视频](docs/subsystems/video.md) |
| 键鼠、虚拟介质、USB-C 协商 | [USB](docs/subsystems/usb.md) |
| KVM 应用、管理面板、UU | [应用](docs/subsystems/application.md) |
| 构建、部署、串口、刷机、系统镜像 | [部署](docs/subsystems/deployment.md) |
| 板子账户密码、SSH/串口登录 | [默认账户](docs/hardware.md#默认账户开发环境) |
| 查证据、记上板结果 | [上板记录索引](docs/bringup/README.md)，只读命中条目 |
| 改完主仓库、提交前 | `python3 -m unittest discover -s tests -p 'test_*.py'`（离线文档/工具/体积等检查） |
