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

### 7. 自编内核与 `/lib` 事故（2026-10-12）

内核构建/安装方法见 [kernel.md](kernel.md)。

**事故**：第一次安装时用 `sudo tar xzf vim4kvm-*.tgz -C / --no-same-owner`。Ubuntu 24.04 的 `/lib` 是指向 `usr/lib` 的符号链接，tar 不带 `--keep-directory-symlink` 时会把它换成真实目录（只剩 `modules/5.15.137-vim4kvm`），`/lib/ld-linux-aarch64.so.1` 消失，所有动态链接程序（ssh、sudo、reboot）都无法运行。

- 串口上已登录的 bash 只能用内建命令；`/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 --library-path /usr/lib/aarch64-linux-gnu /usr/bin/xxx` 可以跑普通程序，但 setuid 失效，sudo 不可用；logind 重启需要 polkit 认证；串口 break + SysRq 无效
- 恢复：用户按 FUNCTION + RESET 进 OOWOW（root busybox），`mount /dev/mmcblk0p2 /mnt/r`，把 `lib/modules/5.15.137-vim4kvm` 移到 `usr/lib/modules/`，`rmdir lib/modules lib && ln -s usr/lib lib`，重启
- 现在用 `tools/kernel-install.sh`，解包后会检查 `/lib` 仍是符号链接

**另一个坑**：`ssh vim4 'echo khadas | sudo -S tee file <<EOF ...'` 在 sudo 凭据已缓存时不读密码，tee 把 "khadas" 写进了 `extlinux.conf`（重启前发现并修复）。写板上配置文件改用 scp 到 /tmp 再 `sudo cp`。

新内核验证：

- `5.15.137-vim4kvm` 启动正常，无失败服务；`Retrieving file: /dtb/amlogic/kvim4n.dtb.overlay.env` 正常读取
- 风扇：`cat /sys/class/fan/temp` → `level0:60 level1:80 level2:100`，mode auto
- `modprobe vfm_cap` → `/dev/video0`（`VFM Capture Tee`）

### 8. HDMI 输入采集（2026-10-12）

**拓扑**：Mac mini HDMI 输出 → VIM4 Micro HDMI 输入（RX port 1）；VIM4 HDMI 输出未接任何设备。

**Mac 不输出信号**：板子上 `hdmiin-demo` 打开源后 HPD 拉高，Mac 读到 EDID（"AML TV"），`ioreg` 中 `HDMI_HPD=Yes` 但 `HDMI_HPD-Debounced=0`，RX 端 `cable clock = 0`。原因是 Mac 上正在使用屏幕共享的高性能虚拟显示器（CoreGraphics 只有一个 Screen Sharing Virtual Display），物理 HDMI 不启用。退出后 Mac 立即输出，RX 锁定 `3840x2160@60 YUV420 10bit`（之后 Mac 也会切到 4K30/RGB/YUV444 等模式，RX 都能锁定）。

调试用：`echo "hpd0 1" > /sys/class/hdmirx/hdmirx0/debug` / `hpd1 1` 软件拔插 port 1（最后一个参数是端口号）；`echo "state 1" > .../debug` 把 port 1 状态打到 dmesg。

**采集链路**：

- tvserver（`tvserver.service`）负责打开 HDMI 源并启动 vdin0；客户端用 `hdmiin-demo`（忽略所有参数，打开即运行；用 `nohup setsid` 后台跑）。**必须在 Mac 已输出信号后再启动**，否则 vdin0 停在 `TVIN_PORT_NULL`，需要重启 `hdmiin-demo`
- 默认 `tvpath { vdin0 amlvideo2.0 deinterlace amvideo }`；改为无下游的 standalone：先停 `hdmiin-demo`，`echo rm tvpath > /sys/class/vfm/map; echo add tvpath vdin0 vfm_cap > /sys/class/vfm/map`，再启动 `hdmiin-demo`
- vfm_cap 的 V4L2 mmap 缓冲只是 4KB 流控令牌，帧数据要在 DQBUF 后用 `VFM_CAP_IOC_GET_DMABUF` 取 DMA-buf fd 再 mmap（`test_dmabuf`）；`v4l2-ctl --stream-to` 拿不到数据
- vdin0 默认 `tv_bit_mode = 0x235`，4K 时输出 Amlogic 40-bit packed 422 10bit（fourcc `AMLY`，非标准，按常规位序解不对）。KVM 只需 8bit：`echo "color_depth_support 0x1" > /sys/class/vdin/vdin0/attr` 后重新开源，输出 **UYVY 3840x2160**，`ffmpeg -f rawvideo -pix_fmt uyvy422` 可直接转换
- 以上已固化为 `tools/hdmi-capture.sh`

**内核 bug（已修复）**：合入的 "Fix vdin1 stuck state" 补丁在 `vdin_v4l2_release()` 中遇到 DEC 已启动就强制 `vdin_v4l2_stop_tvin()`，不区分启动者——只要有进程 `v4l2-ctl -d /dev/video70 --info`，tvserver 启动的 vdin0 就被停掉且 vsync 中断不再恢复（`irq_cnt: 0`）。修正为仅在 V4L2 工作模式且关闭的是 vb2 队列 owner 时强停。

### 下一步

- 8bit 输出固化到 dts（`tv_bit_mode`），或在 vfm_cap/用户态处理 AMLY
- 不依赖 tvserver/`hdmiin-demo` 的开源方式（直接 ioctl `/dev/vdin0` + `/dev/hdmirx0`）
- 编码：aml-streambox 的 gst-plugin-venc（amlvenc）/ libencoder，评估移植
- 把 gadget 改为 HID 键盘/鼠标 + ECM/NCM（macOS 不认 RNDIS）
- 确认 VIN 供电下 USB-C OTG 数据功能正常
