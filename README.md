# vim4-kvm

把 Khadas VIM4（Amlogic A311D2）做成 IP-KVM 专用主机：Ubuntu 24.04 + 板载 HDMI 输入采集 + USB-C OTG 模拟键鼠/U 盘。

## 目录

| 路径 | 内容 |
|---|---|
| [docs/hardware.md](docs/hardware.md) | 硬件接口、串口接线、供电与 KVM 相关的硬件约束 |
| [docs/bringup-log.md](docs/bringup-log.md) | 上板记录（按时间顺序，含踩坑） |
| `tools/uart-run.py` | 通过串口在板子上执行命令并取回输出 |
| `tools/uart-log.py` | 只读抓取串口日志（可选发送一条命令，如重启） |
| `tools/oowow-flash.sh` | 在 OOWOW 下通过串口把镜像写入 eMMC（下载 → 校验 → 写入 → md5 验证） |
| `tools/kernel-install.sh` | 板上安装自编内核包，设为默认并保留 `Stock` 启动项 |
| `tools/hdmi-capture.sh` | 板上经 vfm_cap 抓一帧 HDMI 输入存为 PNG |
| [docs/kernel.md](docs/kernel.md) | 内核构建、安装、回退 |
| `logs/` | 本地串口日志（不入库） |

## 开发环境（Mac mini M4）

- 串口：Sipeed USB to Dual Uart，UART0 = `/dev/cu.usbserial-100`，921600 8N1
- 交互串口：`brew install tio && tio -b 921600 /dev/cu.usbserial-100`（退出 `Ctrl-t q`）
- SSH：`ssh vim4`（`~/.ssh/config` 中 `Host vim4` → `khadas@192.168.50.210`，密钥 `~/.ssh/id_ed25519_vim4_kvm`）

```bash
tools/uart-run.py 'uname -a'                       # 串口执行命令
tools/uart-log.py -t 150 -o logs/boot.log --send 'sync; reboot'   # 重启并抓启动日志
tools/oowow-flash.sh --yes                          # 在 OOWOW 中重装默认 Ubuntu 镜像（会清空 eMMC）
```

## 当前状态

- [x] 串口控制台
- [x] 刷入 Ubuntu 24.04.3 Server（fenix 1.7.5，kernel 5.15.137）
- [x] SSH 免密登录
- [x] 自编内核 `5.15.137-vim4kvm`（[vim4-kvm/common_drivers](https://github.com/vim4-kvm/common_drivers) `vim4-kvm-5.15`）：风扇阈值 60/80/100、vfm_cap
- [x] HDMI 输入采集：vdin0 → vfm_cap，4K60 UYVY 抓帧（见 `docs/bringup-log.md` §8）
- [ ] OTG gadget 改为 HID 键鼠 + ECM/NCM（macOS 不支持 RNDIS）
- [ ] KVM 软件栈（先移植 PiKVM kvmd，后续评估 JetKVM 风格 Go + WebRTC + amlvenc）
