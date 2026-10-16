# vim4-kvm

把 Khadas VIM4（Amlogic A311D2）做成 IP-KVM 专用主机：Ubuntu 24.04 + 板载 HDMI 输入采集 + USB-C OTG 模拟键鼠/U 盘。

## 目录

Agent 入口见 [AGENTS.md](AGENTS.md)（任务路由），经验记录见 [LESSONS.md](LESSONS.md)。
当前目录即主仓库，运行 `python3 tools/workspace.py bootstrap` 克隆缺失子仓库；
布局与冲突处理见 [工作区说明](docs/workspace.md)。

| 路径 | 内容 |
|---|---|
| [docs/tools.md](docs/tools.md) | 全部脚本的运行位置、对板子的影响和文档入口 |
| [docs/subsystems/](docs/subsystems/) | 内核、音视频、USB、应用、部署的当前约定 |
| [docs/hardware.md](docs/hardware.md) | 硬件接口、串口接线、供电与默认账户 |
| [docs/bringup/](docs/bringup/README.md) | 上板记录：每条一个文件，先查索引 |
| `tools/` | 构建、部署、串口、回归与测量脚本 |
| `packaging/` | Ubuntu 组件包、内核包与候选镜像组装 |
| `board/` | 板级 systemd 服务、udev 规则、`install.sh` |
| `tests/` | 离线单元测试（不访问板子） |
| `logs/` | 本地日志与测试证据（不入库） |

## 开发环境（Mac mini M4）

可复现构建输入与 Ubuntu 组件打包入口见 [docs/ubuntu-build.md](docs/ubuntu-build.md)。

- 串口：Sipeed USB to Dual Uart，UART0 = `/dev/cu.usbserial-100`，921600 8N1
- 交互串口：`brew install tio && tio -b 921600 /dev/cu.usbserial-100`（退出 `Ctrl-t q`）
- SSH：`ssh vim4`（`~/.ssh/config` 中 `Host vim4` → `khadas@192.168.50.210`，密钥 `~/.ssh/id_ed25519_vim4_kvm`）
- 默认账户：khadas/khadas、root/khadas（原厂值，开发环境未改，见 [docs/hardware.md](docs/hardware.md#默认账户开发环境)）

板上更新组件：`python3 tools/board.py deploy --exclusive --packages build/packages/VERSION`（见 [docs/board-tools.md](docs/board-tools.md)）

采集编码示例：`gst-launch-1.0 -e vfmcapsrc ! queue ! amlvenc bitrate=8000 ! video/x-h264 ! h264parse ! mp4mux ! filesink location=cap.mp4`

```bash
tools/uart-run.py 'uname -a'                       # 串口执行命令
tools/uart-log.py -t 150 -o logs/boot.log --send 'sync; reboot'   # 重启并抓启动日志
tools/oowow-flash.sh --yes                          # 在 OOWOW 中重装默认 Ubuntu 镜像（会清空 eMMC）
```

## 当前状态

管理面板 **http://192.168.50.210**（[vim4-manager](vim4-manager/README.md)）选择开机启用的
KVM 应用并查看板子状态；NanoKVM、JetKVM（`kvm/`）、One-KVM、PiKVM（`kvmd/`）共用 8080，
同一时间只运行一个。各应用的功能覆盖与验证边界以其 VIM4.md 为准，
板级能力见 [docs/subsystems/](docs/subsystems/)，历史证据见上板记录。

## 许可证

主仓库以 [GPL-3.0](LICENSE) 发布。各子仓库保留各自许可证：fork 沿用上游许可证，
vim4-manager 为 GPL-3.0，gst-plugin-vfmcap 为 LGPL-2.1-or-later。
