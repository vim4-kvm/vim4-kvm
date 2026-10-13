# vim4-kvm

把 Khadas VIM4（Amlogic A311D2）做成 IP-KVM 专用主机：Ubuntu 24.04 + 板载 HDMI 输入采集 + USB-C OTG 模拟键鼠/U 盘。

## 目录

Agent 入口见 [AGENTS.md](AGENTS.md)，经验记录见 [LESSONS.md](LESSONS.md)。
当前目录即主仓库，运行 `python3 tools/workspace.py bootstrap` 克隆缺失子仓库；
布局与冲突处理见 [工作区说明](docs/workspace.md)。

| 路径 | 内容 |
|---|---|
| [docs/hardware.md](docs/hardware.md) | 硬件接口、串口接线、供电与 KVM 相关的硬件约束 |
| [docs/bringup-log.md](docs/bringup-log.md) | 上板记录（按时间顺序，含踩坑） |
| `tools/workspace.py` | 克隆/查看子仓库，本地构建 |
| `tools/ubuntu-build.py` | Docker 中构建 Ubuntu ARM64 组件包 |
| `tools/ubuntu-image.py` | 内核包与整机镜像组装（OrbStack） |
| `tools/board.py` | 组件包部署、冒烟检查、远程进入 OOWOW、校验刷机（见 [docs/board-tools.md](docs/board-tools.md)） |
| `tools/uart-run.py` | 通过串口在板子上执行命令并取回输出 |
| `tools/uart-log.py` | 只读抓取串口日志（可选发送一条命令，如重启） |
| `tools/oowow-flash.sh` | 在 OOWOW 下通过串口把镜像写入 eMMC（下载 → 校验 → 写入 → md5 验证） |
| `tools/kernel-install.sh` | 板上安装自编内核包，设为默认并保留 `Stock` 启动项 |
| `tools/hdmi-capture.sh` | 板上经 vfm_cap 抓一帧 HDMI 输入存为 PNG |
| `tools/hdmi-setup.sh` | 配置 vdin0（8bit、NV21 硬件缩放、线性写入）+ vfm_cap standalone 并打开 HDMI 源 |
| `tools/kvm-gadget.sh` | USB gadget：HID 键盘 + 绝对/相对鼠标 + NCM |
| `board/` | 板上安装：systemd 服务、udev 规则、`install.sh` |
| [docs/kernel.md](docs/kernel.md) | 内核构建、安装、回退 |
| `logs/` | 本地串口日志（不入库） |

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

USB-C 单线供电与键鼠数据的开机初始化见 [docs/usb-pd.md](docs/usb-pd.md)。
`board/install.sh` 会编译并启用 PD 服务；已在 Mac 上验证整机重启后自动枚举和实际输入。

网页入口：**http://192.168.50.210:8080**。应用代码位于子目录 `NanoKVM-Pro/` 仓库的
`vim4` 分支，构建安装见其中 `VIM4.md`。`nanokvm.service` 以 khadas 运行，
已验证整机重启后自动恢复视频和键鼠。当前网页使用本地免密码模式。
管理面板 **http://192.168.50.210**（[vim4-manager](vim4-manager/README.md)）可切换开机启用的
NanoKVM-Pro 或 JetKVM（`kvm/`）界面，并查看板子状态；两者共用 8080，同一时间只运行一个。

- [x] 串口控制台
- [x] 刷入 Ubuntu 24.04.3 Server（fenix 1.7.5，kernel 5.15.137）
- [x] SSH 免密登录
- [x] 自编内核 `5.15.137-vim4kvm`（[vim4-kvm/common_drivers](https://github.com/vim4-kvm/common_drivers) `vim4-kvm-5.15`）：风扇阈值 60/80/100、vfm_cap
- [x] HDMI 输入采集：vdin0 → vfm_cap，4K60 UYVY 抓帧（见 `docs/bringup-log.md` §8）
- [x] 采集→硬件编码：`vfmcapsrc ! amlvenc`，1080p60 H.264 零拷贝（[gst-plugin-vfmcap](https://github.com/vim4-kvm/gst-plugin-vfmcap)）
- [x] OTG gadget：HID 键盘 + 绝对/相对鼠标 + NCM（Mac 键鼠实测通过；NCM IP 通信待验证）
- [x] NanoKVM-Pro 网页 + WebRTC：默认 4K H.264 12Mbps、浏览器键鼠输入、刷新重连及整机重启；4K60 输入下接收约 60fps，播放仍有少量丢帧，支持配置回退到 1080p/720p
- [ ] 音频、虚拟介质、视频设置与热插拔恢复
