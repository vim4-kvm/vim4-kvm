# VIM4 硬件笔记

## 板卡信息

| 项目 | 值 |
|---|---|
| 型号 | Khadas VIM4（`/proc/device-tree/model` = `Khadas VIM4`，OOWOW 报告 `ver:0005`） |
| SoC | Amlogic A311D2（T7），4×A73 2.2GHz + 4×A53 2.0GHz |
| 内存 / 存储 | 8GB / 32GB eMMC（`BJTD4R`） |
| 网口 MAC | `c8:63:14:74:70:0d`（路由器已固定 IP 192.168.50.210） |
| OOWOW 设备名 | `vim4-0008c`（OOWOW build 241112，存于 SPI flash） |

## 与 KVM 相关的接口

| 接口 | 用途 | 备注 |
|---|---|---|
| Micro HDMI 输入（Type-D） | 采集被控机画面 | HDMI RX **port 1**，进 vdin0。`/dev/video71`（vdin1）是显示输出回写，不是 HDMI 输入；采集走 tvserver 打开源 + vfm_cap（见 bringup-log §8）。官方称 HDMI 输出须接显示器，实测未接时 vdin0 + vfm_cap 可正常采集 |
| USB-C（USB2.0 OTG + PD） | 模拟键鼠 / 虚拟 U 盘 / USB 网卡 | UDC = `fdd00000.crgudc2`。**同时也是 9–20V PD 供电口** |
| VIN（背面） | 9–20V 供电 | 作为 KVM 使用时 USB-C 要接被控机，必须改由 VIN 供电 |
| HDMI 输出 | 本地显示 / 挂假负载 | |
| 40-pin GPIO | 串口、ATX 电源控制 | |
| M.2（PCIe 2.0 x1） | NVMe | 未插盘时内核会报 `amlogic-pcie-v2 ... error -110`，无害 |

视频编码：Amlogic 硬件编码器走 GStreamer `amlvenc`，**不是标准 V4L2 M2M**，PiKVM ustreamer 的硬编码路径无法直接用。

## 按键

| 操作 | 效果 |
|---|---|
| 按住 FUNCTION → 短按 RESET → 松开 FUNCTION | 进入 OOWOW（先拔出 SD 卡，SD 启动优先级最高） |
| 2 秒内按 FUNCTION 3 次 | MaskROM 模式 |
| RESET | 硬复位 |

## 串口调试

VIM4 调试串口：**921600 8N1**，内核 `console=ttyS0,921600`。

Khadas 40-pin 编号**与树莓派不同**：一排为 1–20，另一排为 21–40。17/18/19 在 1–20 那排的末端，远离 1/2 脚（5V）。

| VIM4 引脚 | 功能 |
|---|---|
| 1, 2 | 5V（不要碰） |
| 15 / 16 | UART_E RX / TX（备用串口） |
| **17** | GND |
| **18** | UART_RX（Linux_Rx） |
| **19** | UART_TX（Linux_Tx） |
| 20 | 3V3 |

### 串口模块：Sipeed USB to Dual Uart

- GD32F150GB 主控，USB 枚举为 `VID 0x0403 / PID 0x6010`（FT2232 兼容），macOS 免驱
- macOS 节点：`/dev/cu.usbserial-100` = UART0，`/dev/cu.usbserial-101` = UART1
- 双串口均最高 3Mbps，逻辑电平 3.3V
- 2×6P 排针（上排 UART0，下排 UART1）：

```
上排 UART0:  GND  3V3  TX0  RX0  BOOT0  RST0
下排 UART1:  GND  5V   TX1  RX1  BOOT1  RST1
```

- BOOTx/RSTx 由 DTR/RTS 直接控制（UART0：DTR→RST0，RTS→BOOT0；UART1：DTR→BOOT1，RTS→RST1），**不要接到 VIM4**，否则打开串口时可能误触发
- 区分上下排：插上 Mac 后量第 2 列对 GND 电压，3.3V 的为 UART0

### 接线

| 模块（UART0 排） | VIM4 |
|---|---|
| GND | Pin 17 |
| TX0 | Pin 18 |
| RX0 | Pin 19 |
| 3V3 / BOOT0 / RST0 | 不接 |

无输出时先对调 18/19；乱码先查 GND。

### 已知坑

- Sipeed 模块的 Type-C 口用 C-to-C 线时可能不被 Mac 枚举（`USB-C@N` 显示 `ConnectionActive=Yes` 但没有 USB 设备），换线/换接法后正常。
- macOS 自带 `stty` 不能设置 921600，`tools/uart-run.py` 用 `IOSSIOSPEED` ioctl 设置波特率。

## 推荐的开发拓扑

Mac mini 同时充当被控机，一台机器即可验证 KVM 全链路：

```
               Ethernet (192.168.50.210)
  Mac mini M4 ───────────────────────────────── VIM4
     │ USB-UART ── GPIO 17/18/19 (921600) ────────┤
     │ HDMI out ── micro-HDMI ─────── HDMI-IN ────┤
     │ USB ──────── USB-C (OTG: HID/ECM/MSD) ─────┤
                                 12V DC ── VIN ───┤
                      HDMI dummy plug ── HDMI-OUT ┘
```
