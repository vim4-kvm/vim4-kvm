# 上板记录

## 2026-10-12 串口 + 重装 Ubuntu

### 1. 串口接通

- 模块：Sipeed USB to Dual Uart，UART0 → VIM4 Pin 17/18/19（见 [hardware.md](hardware.md#串口调试)）
- Mac 侧 `tio` 3.9（`brew install tio`），节点 `/dev/cu.usbserial-100`，921600
- 第一次用 C-to-C 线连接模块时 Mac 不枚举，换连接后出现 `/dev/cu.usbserial-100/101`

### 2. 出厂系统（已被清除）

板子 eMMC 上原本不是 Khadas 官方 Ubuntu，而是一个 "streambox" 定制 Yocto 固件：

| 项目 | 内容 |
|---|---|
| 系统 | Poky (Yocto) 4.0.18 kirkstone，kernel `5.15.137-amlogic`，Android 风格分区（p1–p19） |
| 服务 | `/usr/bin/one-kvm`（One-KVM）、`streambox-tv`、`streambox-settings`（Python）、weston、hostapd |
| USB gadget | configfs 名为 `one-kvm`，功能 `hid.keyboard` + `hid.usb1`，UDC `fdd00000.crgudc2` |
| Wi-Fi | `wlan1` AP：SSID `streambox-setup-<mac>`，192.168.172.1/24 |
| 串口 | `root` 免密 shell |

说明这块板（同一内核 5.15 + `/dev/video71` + crgudc2）已被别人做成过 KVM 产品，硬件路径可行。按需求未备份，直接重装。

### 3. 进入 OOWOW

- 按住 FUNCTION → 短按 RESET → 松开，串口可见 `Load BL2E From: SPINOR`、`boot_source=spi kresq_type=spi`
- OOWOW build 241112，设备名 `vim4-0008c`，串口为 root shell（输入 `system` 进菜单）
- 进入 OOWOW 后 eth0 自动 DHCP（当时 192.168.50.210），`usb0` = 172.22.1.1

### 4. 写入镜像（踩坑）

目标镜像：`vim4-ubuntu-24.04-server-linux-5.15-fenix-1.7.5-250925.img.xz`（542,748,672 字节，解压 3,338,666,516 字节）
来源：`https://dl.khadas.com/.images/vim4/`

| 尝试 | 结果 |
|---|---|
| `curl URL \| curl -T . 127.0.0.1/api/disk/write/mmc.xz`（流式） | 卡死：下载停在 ~22MB，`pixz` CPU 时间为 0，eMMC 无写入。OOWOW 的 HTTP 接口不处理 chunked 上传 |
| 官方 `curl 127.0.0.1/shell/write \| sh -s - /tmp/img.xz` | 失败：OOWOW 没有 `file` 命令，脚本误判格式走了 zstd 分支，**执行了 gpt_clean 把分区表清掉**，未写入镜像 |
| 先下载到 `/tmp`（tmpfs 7GB）→ `xz -t` → `curl -T /tmp/img.xz 127.0.0.1/api/disk/write/mmc.xz` | 成功，约 1 分钟写完。响应体是 `Request Entity Too Large`，但实际已完整写入 |

验证：`xz -dc img | md5sum` 与 `head -c 3338666516 /dev/mmcblk0 | md5sum` 一致（`139f09976b9324ed28f99b509991d9a0`）。

以上流程已固化为 `tools/oowow-flash.sh`。

### 5. 首次启动 Ubuntu

- U-Boot 2019.01（Sep 25 2025），`boot_source: emmc`，`otg_device=1`
- `Ubuntu 24.04.3 LTS Khadas ttyS0`，默认账号 `khadas / khadas`
- 无害报错：`amlogic-pcie-v2 ... failed with error -110`（无 NVMe），`aml_card_probe error ret:-517`（声卡延迟探测）
- 分区：p1 FAT32 240M（boot），p2 ext4，首次启动自动扩展到 29G

系统信息：

```
IMAGE_VERSION=1.7.5-250925
UBOOT_GIT_VERSION=khadas-vims-u-boot-2019.01-v1.7.5-release
LINUX_GIT_VERSION=khadas-vims-linux-5.15-v1.7.5-release
linux-image-amlogic-5.15 1.7.5
linux-u-boot-vim4-vendor 1.7.5-2019.01
```

USB gadget（默认 `usb-gadget-khadas.service`，enabled）：configfs `khadas`，`ffs.adb` + `rndis.0`，VID/PID `0x18d1/0x4e26`，UDC `fdd00000.crgudc2`。

`/dev/video71` 存在；`v4l2-ctl` 未安装。

### 6. SSH

- `sudo systemctl enable --now ssh`（镜像默认未启用）
- Mac 新建密钥 `~/.ssh/id_ed25519_vim4_kvm`，写入 `khadas` 的 `authorized_keys`
- `~/.ssh/config` 增加 `Host vim4`；路由器已为 MAC `c8:63:14:74:70:0d` 固定 IP 192.168.50.210

### 下一步

- 安装 `v4l-utils`，用 Mac mini HDMI 输出验证 `/dev/video71` 采集
- 把 gadget 改为 HID 键盘/鼠标 + ECM/NCM（macOS 不认 RNDIS）
- 确认 VIN 供电下 USB-C OTG 数据功能正常
