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

### 9. 采集→编码链路与 USB gadget（2026-10-12）

**结论**：HDMI 1080p60 → vdin 硬件缩放+NV21 → vfm_cap DMA-buf → `vfmcapsrc` → 原厂 `amlvenc`（DMA-buf 输入，零拷贝）→ H.264，实测 60fps，gst 进程约 6% CPU。

**streambox 用户态没有照搬**：`libvfmcap` / `streamboxsrc` / `vfmcapsrc` 都绑定 Vulkan（Mali）把 10bit AMLY 转 NV12/P010（约 1.2 万行）。让 vdin 直接写 8bit NV21 后不需要这层，改为自写的 [vim4-kvm/gst-plugin-vfmcap](https://github.com/vim4-kvm/gst-plugin-vfmcap)（约 400 行，DQBUF → GET_DMABUF → GstDmaBufMemory，token 立即归还）。编码直接用板上原厂 `gstreamer-aml` 的 `amlvenc`（已支持 dmabuf 输入），不需要移植 streambox 的 gst-plugin-venc / libencoder。

vdin0 运行时设置（`tools/hdmi-setup.sh`，由 `vim4-kvm-hdmi.service` 开机执行）：

| `/sys/class/vdin/vdin0/attr` | 作用 |
|---|---|
| `color_depth_support 0x1` | 只写 8bit（默认 4K 走 10bit packed AMLY） |
| `no_swap_en 1` | 关闭 128bit 内 64bit 字交换 + 大端写入。默认格式是给显示层读的，CPU/编码器直接读 NV21 时每 8 字节反序（看起来像水平镜像） |
| `conversion W H 8` | vdin 硬件缩放到 W×H 并输出 NV21（`TVIN_NV21=8`） |

**修复的 bug**：

- vfm_cap：NV12/NV21 的 canvas 大小检查只算 Y 平面，每帧都被当成越界丢掉，并每帧发 SOURCE_CHANGE
- amvenc_multi（`vpu_multi.c`）：T7 上 `vpu_clk_disable()` 调的是 `vdec_poweron()` 而不是 `vdec_poweroff()`，WAVE 电源引用计数只增不减，电源域从不断电。编码中途被 kill 后 Wave521 固件卡死（`vp5xx_vcpu_status PC=0x112c` 不变），之后所有编码初始化失败，`rmmod` 重载也无效，只能重启。修复后 `kill -9` 编码进程后可立即重新编码（含 `/tmp/vpu_mutex.map` 残留）
- vfmcapsrc：分辨率变化不一定先于新帧发出 SOURCE_CHANGE，帧大小与当前格式不符时主动重新查询并重新协商

**验证**：HDMI 拔插（`hpd0 1` / `hpd1 1`）期间管线暂停，恢复后继续出帧；1080p→720p→1080p 切换，编码器随 caps 重建，输出裸 H.264 无错误（matroskamux 不支持中途改分辨率，属 mux 限制）。

**USB gadget**（`tools/kvm-gadget.sh`，`vim4-kvm-gadget.service`，替代并禁用 `usb-gadget-khadas.service` 的 adb+rndis）：

- `/dev/hidg0` 键盘（boot protocol，8 字节输入 + 1 字节 LED 输出）
- `/dev/hidg1` 绝对坐标鼠标（5 键，X/Y 0..32767，滚轮，6 字节）
- `/dev/hidg2` 相对鼠标（boot protocol，4 字节，BIOS/UEFI 用）
- `ncm.usb0`（macOS / Linux / Windows 10+ 原生驱动）
- 描述符参考 One-KVM 的 `report_desc.rs`，键盘改为带 LED 输出；用离线解析校验了集合平衡和报告长度
- 板上没有 `xxd`，描述符用 `printf '%b'` 写入（`%` = 0x25 会被普通 printf 当格式符）

### 10. Mac USB HID 实测与描述符修复（2026-10-12）

PD 实验后 Mac 已枚举复合设备，板上 UDC 为 `configured`，但这不代表 HID 可用。
`kvm-gadget.sh` 使用 `/bin/sh`，Ubuntu 的 dash 不解析 `printf '%b'` 的
`\xNN` 转义，实际 report_desc 是 ASCII 文本。之前在 bash 下验证 printf
不能证明该脚本正确。改为 Python `bytes.fromhex()` 写二进制，并修正键盘
Usage Maximum 的两字节项目前缀（`2a ff 00`）。此项取代第 9 节关于 printf 的结论。

通过串口部署后，板上脚本 SHA-256 与本地一致；三个描述符分别为 65、76、62 字节。
重启 gadget 服务后，Mac hidutil 注册了一个键盘和两个鼠标，实测：

- 相对鼠标：发送 X=12，Mac 光标从 (905,1055) 移至 (913,1055)。
- 键盘：按住右 Shift，Mac NSEvent.modifierFlags 为 131072；释放后为 0。
- 绝对鼠标：发送 X=Y=16384，Mac 光标到 (960,540)。
- 板上 `usb0` 原为 DOWN，手动启用后 Mac `en8` 从 inactive 变为 active。
  IPv4 LAN SSH 和 USB IPv6 SSH 在本次运行环境均报 No route to host，未验证 NCM 的 IP 通信。

PD 程序仍是实验工具，尚未作为开机服务安装；整机重启自动协商未验证。
本次只重启 gadget 服务，未重新协商 PD，也未重启板子。

### 11. PD 开机初始化固化（2026-10-12）

新增 `tools/usb-pd-init.c`、`board/vim4-kvm-pd.service`，详见 [usb-pd.md](usb-pd.md)。
编译启用 `-Wall -Wextra -Werror`；测试覆盖 1.5A/3A 请求、电流上限、
拒绝非 5V、非固定 PDO 和零电流。`board/install.sh` 安装并启用服务，
下次启动在 gadget 创建之后进行有限的 20 秒 PD 交接，失败不自动重试。

保留同一根 Mac USB-C 供电/数据线，执行整机重启后验证：

- `vim4-kvm-pd` Result=success、ExecMainStatus=0。
- 主机返回 Accept、PS_RDY，日志记录 5V/3A 和 `PD bootstrap complete`。
- UDC 为 `configured`，Mac 自动重新注册一个键盘、两个鼠标。
- 右 Shift 按下/释放，Mac modifierFlags 为 131072/0；绝对坐标报告将光标移至 (480,810)。

启动日志保存于本地 `logs/pd-autoboot.log`（不入库）。本次通过串口部署和验证，
未刷写 U-Boot，未更改 PD 电压，未配置 NCM IP 网络。此验证覆盖正常重启，
不覆盖断电冷启动、主机休眠或不断电热插拔。

### 12. WebRTC 网页 KVM（2026-10-12）

应用仓库为同级 `kvm/`，工作分支 `vim4`。详见其中 `VIM4.md`。
网页地址 **http://192.168.50.210:8080**，本次选择本地免密码模式。
SSH 已恢复，可以直接同步代码和构建；Ubuntu 密码未改。

- `go build -tags vim4` 排除 Rockchip/LVGL，接入 GStreamer appsink。
- 视频路径：vfmcapsrc → amlvenc → h264parse → appsink → WebRTC。
  完整 H.264 帧按 PTS 间隔送入媒体轨道，每个 IDR 重发 SPS/PPS。
- 发现 amlvenc 的 duration 仍为 1/30 秒，即使实际输入为 60fps。
  改用相邻 PTS 后，300 帧媒体时长为 5.017 秒；ffprobe 确认 1080p60。
- 键鼠复用既有 hidg0–2，适配六字节绝对鼠标、四字节相对鼠标。
  应用不改 gadget 和 PD，系统网络、时钟、升级、看门狗仍由 Ubuntu 管理。
- `deploy/vim4/install.sh` 安装 `vim4-kvm.service` 和 HID udev 权限规则。
  服务使用 khadas 用户、video/input 组，配置在 `/var/lib/vim4-kvm/config.json`。
- root 启动编码会崩溃：现有 khadas 所有的 `/tmp/vpu_mutex.map` 在 root
  使用 O_CREAT 打开时返回 EACCES。编码测试和服务统一用 khadas，保留共享 /tmp。

验证：ARM64 `go test -tags vim4 ./...` 全部通过，网页 TypeScript 与构建通过。
Chrome 3 秒解码约 180 帧；通过 WebRTC RPC 和网页实际 Shift 按键分别验证
Mac modifierFlags 0 → 131072 → 0。绝对鼠标到 (960,540)，相对鼠标向右移动。
浏览器刷新可以重新打开编码器并恢复视频。

整机重启后 boot ID 改变，PD/HDMI/gadget/web 四个服务均 active，PD Result=success，
UDC=configured，hidg0–2 权限自动恢复为 root:input 0660。
浏览器再次解码 1080p 视频（3 秒 181 帧，新增丢帧 2），网页 Shift 与两种鼠标再次通过。
此数据不是延迟测量，也不代表零丢帧。

### 13. 4K 视频输出（2026-10-12）

采集默认值改为 3840×2160，保持 8-bit NV21 和 DMA-buf 路径；应用 H.264
码率从 8Mbps 提高到插件上限 12Mbps。没有调整编码器时钟。
`/etc/default/vim4-kvm-hdmi` 可设置 HDMI_WIDTH/HDMI_HEIGHT，支持
3840×2160、1920×1080、1280×720，其他尺寸在修改硬件状态前拒绝。
切换时先停止 web 服务，再重启 HDMI 服务，最后启动 web 服务并刷新页面。

4K60 输入下，独立编码 600 帧耗时 10.126 秒，ffprobe 解码确认
3840×2160、600 帧、60/1。初次 Chrome 测量在 15 秒内视频帧计数增加
901，丢帧计数增加 41；传输接近 60fps，不代表播放零丢帧。
官方规格标称 4K50 编码，此处仅记录本板实测；复杂运动画质还受 12Mbps 限制。

部署 12Mbps 版本并移除临时 /run 覆盖配置后整机重启，四项服务均 active、
UDC=configured，Chrome 自动得到 3840×2160 视频。预热 5 秒后的 10 秒内
帧计数增加 601、丢帧增加 30，实际呈现约 57fps；刷新后恢复 4K。
此次没有完成复杂运动内容压测。采集相关 Go 测试、ARM64 构建、shell 语法和
无效分辨率拒绝检查通过。
配置回退至 1080p 后浏览器确认 1920×1080；删除覆盖配置后恢复默认 4K。

### 14. 自动风扇和 Wave521 提频（2026-10-12）

主内核 fork 为 `vim4-kvm/linux`，基于 Khadas 官方 4e557e233，在 VM 的
`vim4-kvm-5.15` 分支维护。没有切换到第三方整套内核。后续系统镜像应使用
本组织官方 fork 的固定提交和本仓库的部署配置，禁止依赖未记录的板上手工修改。

`khadas-mcu.ko` 增加百分比自动风扇曲线，并修正高温/传感器错误时全速、
手动模式不受阈值写入影响、同步取消延迟任务。保留原始作者，新增修正另作提交。
策略函数的单调性、范围、非紧急步长和紧急全速测试通过；模块在 ARM64 构建成功。
整机重启后自动模式和 speed 接口生效；板上测试手动 40%、拒绝 101%、降低
高温阈值触发立即 100% 均通过，之后恢复原来的 60/80/100°C 阈值和自动模式。

确认编码器配置为 A/B/C=666666666Hz，而原始 B/C=500MHz。
配置来源的核查位置：
[media-modules_5.15.bb](https://github.com/aml-streambox/meta-meson/blob/8dec0d361b225dbe5a253ab090dae7d42179e848/recipes-kernel/media_modules/media-modules_5.15.bb#L229)。
本板运行时 debugfs 三路读回 666666656Hz；不改 CPU、电压和总线频率。
持久配置为 `board/90-vim4-encoder.conf`，安装到 `/etc/modprobe.d/`。

同样 Chrome 无头测试、预热 5 秒后观察 20 秒：默认频率帧计数 +1200、
播放丢帧 +119；提频后 +1200、丢帧 +118。没有观察到播放丢帧改善，
因此不能把浏览器丢帧归因于编码器频率不足。
提频独立编码 1200 帧耗时 20.109 秒，ffprobe 解码确认 3840×2160、60/1、
1200 帧。调速后观测温度约 51°C；这是短期实测，
未覆盖高温环境、长期运行和复杂动态内容压力测试。
安装 modprobe 配置并更新 initramfs 后再次重启，B/C 参数自动为 666666666，
播放时三路实际时钟均为 666666656Hz；自动风扇接口存在、四项 KVM 服务 active，
UDC=configured。无需开机后手工设置频率。
重启后第一次浏览器测试超时，同期日志出现 other-session 页面和来自另一客户端
的会话交接；重试成功，4K 视频 20 秒内帧计数 +1201、丢帧 +64。
不同轮次丢帧波动明显，尚不能给提频带来的播放收益下结论。

### 15. 应用主线调整为 NanoKVM-Pro（2026-10-12）

从 Sipeed 官方仓库创建 `vim4-kvm/NanoKVM-Pro` fork，本地同名目录、工作分支
`vim4`，基线为 3b013bb627a461846a6594f48e01d5a86729ef48。保留官方历史和 GPL-3.0。
该仓库成为后续应用适配主线，现有 JetKVM 版本继续运行，待新版端到端验证后切换。

初步审查确认：Go 后端调用的 libkvm 在已发布仓库中只有会退出的占位实现，
需要用现有 GStreamer 路径实现视频接口；hidg1/hidg2 的相对/绝对鼠标顺序与
当前板子相反。系统更新、USB 重建、存储和网络管理绑定原设备，需逐项适配。
fork 已创建，适配边界记录于应用仓库 VIM4.md；此时尚未构建或部署 NanoKVM。

### 16. NanoKVM-Pro 首阶段部署（2026-10-12）

应用仓库的 `vim4` 构建目标排除占位 libkvm，接入 vfmcapsrc → amlvenc →
h264parse → appsink。H.264 12Mbps、GOP 30，按输入 PTS 计算媒体时间。
最后一个视频连接退出后释放编码器；修复了旧管线关闭过程中，新连接启动请求
被忽略而造成刷新黑屏的问题。捕获失败后按 1 秒间隔重新尝试。

键鼠复用现有 gadget，调整 hidg1/hidg2 映射；限时写入，设备不存在时不再空指针
崩溃。最后一个输入连接关闭时等待已排队报告完成，然后释放按键及鼠标按钮，
保留绝对坐标。网页保留粘贴、虚拟键盘、快捷键、鼠标模式和全屏。
其他设备专用功能尚未启用；API 同样不注册固件更新、USB 重建等操作。

应用路径 `/opt/vim4-nanokvm`，配置 `/etc/kvm/server.yaml`，服务 `nanokvm`，
仍为 khadas 用户和本地免密码模式。网页 **http://192.168.50.210:8080**。
Ubuntu 密码未修改。旧 `vim4-kvm` 应用服务已禁用，HDMI/gadget/PD 服务保持启用。
构建、安装及回退步骤见 NanoKVM-Pro/VIM4.md，部署文件进入该应用仓库。

验证：ARM64 `go test -tags vim4 ./...`、前端 TypeScript/生产构建通过，
原始非 vim4 目标也成功编译（仅编译占位库，未运行）。Go `-race` 在板上无法启动：
ThreadSanitizer 要求 48 位 VMA，当前内核为 39 位；没有宣称竞争检测通过。

整机重启后 NanoKVM/HDMI/gadget/PD 均 active、UDC=configured，浏览器显示
3840×2160，5 秒新增 301 帧、播放丢帧 12。网页实际 Shift 按下/释放对应
Mac modifierFlags 131072/0；绝对鼠标到 (480,810)，相对鼠标向右移动。
刷新后恢复 4K。该结果不代表零丢帧或长时间压力测试通过。

### 下一步

- HDMI 热插拔、分辨率切换、多浏览器交接的 WebRTC 回归验证
- 音频、虚拟介质、视频设置和错误自动恢复
- NCM 的 IP 通信验证；当前网页走 eth0
- 断电冷启动、Mac 休眠和 USB 热插拔验证
- 必要时扩展编码器码率/帧率控制（后续进展见第 17 节）

## 17. NanoKVM 原版视频控件、MJPEG 与 VDIN 缓冲区释放

采用最小侵入适配：继续使用 NanoKVM 原版屏幕菜单、设置窗口和传输模块。
新增 1280×720、1920×1080、3840×2160 的采集分辨率选项；原有码率、GOP、
FPS、JPEG 质量接口接到 VIM4 后端。H.264 仍用 amlvenc，码率限制 1–12 Mbps，
GOP 1–200，FPS 0（跟随输入）或 1–60。UI 滑块结束操作后再重配编码器。
全局参数写入 `/etc/kvm/video.json`；分辨率写入 HDMI 服务的 EnvironmentFile。
受限 root helper 仅接受三档分辨率，Web 服务仍使用 khadas 用户。

MJPEG 复用原版 HTTP multipart 实现，修复由后台线程写已取消请求响应的问题：
请求自己写响应，每个观看者只排队最新 JPEG。旧模式退出不会关闭新模式的编码器。
连续硬件 JPEG 测试只得到 4 帧后停住，因此使用软件 JPEG，最高限制 10fps；
4K 实际速度低于这个上限，不宣称 MJPEG 4K60。

反复切换发现 codec CMA 泄漏：NV21 使用两个 canvas ID，canvas 初始化会缩小
`vf_mem_max_cnt`，停止时却按缩小后的数量释放已分配缓冲区。剩余缓冲区逐次泄漏，
最终日志出现 `Failed to alloc dma buffer amvenc_multi`。修复遍历全部非空分配槽位，
释放后清空指针；修改限于 `vdin_canvas.c`，提交 `common_drivers:a0d3a8546`。

VM 使用既有 gcc-12/5.15.137-vim4kvm 配置增量构建 modules，安装 `aml_media.ko`
并更新 initramfs。第一次重启打断了 initramfs 更新，仍加载旧模块；随后完整重跑
update-initramfs、等待退出成功再重启。新模块 build-id 已通过 sysfs 核对为
`f7adab7ca175365865683fa578a8decf9757e84a`，boot-id
`89911371-09a6-4e5e-9f7c-f7b484fd3e3f`。临时 `.new`/`.dpkg-bak` 已由成功更新清理。

验证：

- 重启保留 1080p；NanoKVM、HDMI、PD、gadget 均 active，UDC=configured。
- Chrome 连续 10 轮 720p→1080p→4K（30 次切换），每次实际解码尺寸正确。
  每轮回到 4K 时 DriverCma 始终 378792 KiB，与基线一致；CmaFree 约 1331288 KiB。
- 原版菜单的三档分辨率、MJPEG/H.264 切换及原版设置 FPS 滑块已实测。
- 30fps H.264 在切换过渡结束后，两个 5 秒窗口分别增加 150、151 帧。
- 两个同时连接的 4K MJPEG 客户端各在 6 秒内收到 34 帧、12279704 字节。
- ARM64 Go 全套测试、VIM4 后端和原版目标编译、前端 TypeScript/生产构建通过。
  新增测试覆盖无效参数不改变采集、JPEG 可解码、旧传输不关闭新会话、慢 MJPEG
  观看者不阻塞其他观看者。未宣称 Go race 检测通过，板上 VMA 限制仍存在。

用户确认只连接 HDMI 和 USB-C，USB-C 同时供电和传输。完整功能接入仍在进行；
音频、虚拟介质、终端/脚本、网络与应用管理等剩余项见 NanoKVM-Pro/VIM4.md。
缺少的 ATX、外接串口、屏幕和灯带应报告未配置，不能映射到无关 GPIO。

## 18. NanoKVM 终端、脚本、网络唤醒与镜像管理

沿用原版菜单、弹窗和 API，增加终端、shell/Python 脚本的上传/前后台执行/删除、
Wake-on-LAN、标题和菜单图标设置。终端以 khadas 运行，shell 退出会关闭 WebSocket；
脚本不再通过拼接 shell 命令执行。WOL 使用 UDP 广播，缓存写入串行化。
原版手动串口界面保留，VIM4 不显示 AX630 固定串口预设；已安装 picocom 并加入
dialout 组，没有外接串口硬件，因此不宣称串口通信实测通过。

镜像存储在 `/var/lib/vim4-kvm/images`，沿用原版分块上传、挂载、校验、删除和 URL
下载界面。未完成上传/下载不会成为可挂载镜像；禁止覆盖或删除正在挂载的文件。
固定 root helper 只接受该目录中的普通 IMG/ISO，以已打开的文件描述符交给 configfs。
不导出 Ubuntu 根盘。CD-ROM 强制只读。板端 gadget 创建但默认不连接 mass_storage.disk0。

USB 实测发现两点：

- CRG 驱动把 OUT context 也声明为 IN，导致省略 HID OUT 端点后产生错误分配；
  修正 capabilities，仅声明硬件固定方向。所有 HID 改用 interrupt IN，键盘 LED
  output 通过 control SET_REPORT。模块 build-id `c6056f5befd206c1a05e40c797895b49bd507aa3`，
  已完整更新 initramfs 并重启。
- 三个 HID + NCM + mass storage 同时使用时，第六个 IN（DCI 12）仍 CONFIG_EP 超时。
  当前挂载镜像时切换掉 NCM，弹出后恢复 NCM，保留 HID function 与 PD 供电契约。
  挂载弹窗明确提示使用以太网/Wi-Fi 管理，不能宣称网卡与镜像盘同时可用。
  configfs 重新枚举时留出 500ms 断开时间，不重新运行 PD 协商。

验证：ARM64 Go 全套测试、两种后端目标编译、前端 TypeScript/生产构建、Python
helper 边界测试通过。真实终端命令及退出、shell/Python 脚本、标题/菜单持久化、
WOL API/缓存、分块上传与乱序拒绝、SHA256、URL 下载、挂载删除保护通过。
WOL 包结构由 UDP 接收测试核对，没有让供电的 Mac 睡眠做唤醒测试。

Mac 已枚举并挂载测试 FAT 镜像与 ISO 光盘；镜像挂载期间，Chrome 实测键盘 Shift
以及绝对/相对鼠标通过，4K H.264 和刷新恢复正常。首次文件读取看似卡住，后查明
macOS tccd 在等待 `com.yetone.magpie` 的 `SystemPolicyRemovableVolumes` 权限弹窗。
因此文件级读写尚未验证，不将其记为驱动传输失败或读写成功；等待用户授权后复测。
测试文件 `vim4-media-check.img/.iso` 留在镜像目录，已弹出，供后续验证。

最终 boot-id `a1cd93b8-a8dd-4c1e-bf92-905c2900569f`；NanoKVM、HDMI、gadget、PD
均 active，UDC=configured。USB gadget 重启会经 Requires 关系停止 PD 服务，再启动
NanoKVM 时会重新执行 PD 引导；仅挂载/弹出镜像不应重启 gadget 服务。

## 19. NanoKVM HDMI 音频、Ubuntu 管理与应用更新

继续保留原版 NanoKVM 菜单、设置页和 API。Ubuntu 差异放在 VIM4 build tag 与
固定 root helper 中，没有引入另一套管理界面。应用仍监听 8080。

- HDMI RX 音频设备为 `hw:AMLAUGESOUND,0`，48kHz 双声道 S16LE。厂商
  `audioserver.service` 独占该设备，部署时禁用；tvserver/HDMI 服务保留。
  ALSA → Opus 96Kbps/20ms → 原版 WebRTC 音轨，最后一个观看者离开后释放设备。
  Mac 通过 CoreAudio 定向向 AML TV 输出 440Hz，不改变系统默认输出；VIM4
  原始采样测得 440Hz 幅度约 3277。Chrome 原版音量滑块取消默认静音后，在
  4K 画面下收到并解码非静音音频（约 6 秒 278 包、293280 个采样）。
  USB 麦克风注入、MJPEG 音频尚未实现。
- 原版设备设置接入 NetworkManager 的 eth0 DHCP/静态 IPv4、Wi-Fi 扫描/连接/
  断开，以及 Ubuntu SSH、Avahi mDNS、主机名、时区、chrony 同步和重启。
  Wi-Fi 密码经 stdin 传入；失败的 Ethernet reapply 会恢复原 profile。
  板上读取、同值 DHCP/主机名/时区、启用服务、非法输入拒绝通过；单元测试覆盖
  地址边界、SSID 转义和回滚。没有改动现有 IP，没有关闭 SSH；未实际切换网段，
  Wi-Fi 当前未连接且没有凭据，因此不宣称入网成功。
- 原版账户页支持修改 Web 账户，使用 bcrypt 与 0600 原子文件写入，不调用
  Ubuntu passwd。隔离 API 测试验证新账户可校验且没有明文密码。真实账户密码
  未改，认证仍保持用户原先禁用的状态；仅修改 Web 密码不会自动启用登录认证。
- 新增可复现的 `NanoKVM-Pro/deploy/vim4/package.py`，生成 arm64
  `vim4-nanokvm` DEB、原版 tar.gz 更新包和 latest manifest。包含应用、前端、
  helper、sudoers 和服务；保留配置、账户与镜像。依赖既有 VIM4 内核、插件、
  HDMI/gadget/PD 服务，不是完整刷机镜像。拒绝 AX630 固件和其他平台包。
  未配置公开更新源，清除自定义源不会回退到原机 CDN。
- 实际调用原版手动 inspect/confirm 接口安装 `1.0.1+vim4.20261012`，任务
  succeeded 在自动重启服务后保留。通过板上临时 loopback HTTP 更新服务器，
  在线下载校验并安装 `1.0.2+vim4.20261012`，随后清除测试源。最终文案包为
  `1.0.3+vim4.20261012`。更新只重启应用，不重启板子。DEB 安装不是事务回滚，
  发布包应来自可信构建；当前没有公开发布更新服务。

VIM4 与默认目标 Go 测试、两种后端编译、Python helper 测试、前端 TypeScript/
生产构建通过。默认测试以 `LD_LIBRARY_PATH=$PWD/dl_lib` 加载原版 stub，不能代表
AX630 硬件验证。Chrome 原版设备、账户和更新设置无 pageerror/接口 404。
部署源与验证结果均保留在仓库，供后续系统镜像构建使用。

## 20. 4K60 编码预算与局域网 RTP 分包

从官方 `khadas/multimedia-gst-plugin-venc` 创建 org fork
`vim4-kvm/gst-plugin-venc`，本地 `vim4` 分支起点 `997f264`。修复 amlvenc
framerate 属性只能到 30 的限制，允许 0–120；0 使用输入 caps 的帧率，未知时
回退 30，分数帧率四舍五入到编码库整数 API。初始化码控和逐帧 metadata 使用
同一个值。原版权声明保留，没有替换为第三方实现。

vfmcapsrc 当前报告不定帧率，因此 NanoKVM 创建 pipeline 时读取 HDMI RX 的
`Frame Rate`（单位 1/100 fps），与用户 drop-only FPS 上限取较小值后传给编码器。
同尺寸但源帧率变化、且没有 caps 变化时需要重开采集。GOP 120、performance、
现有 RTP 时间戳/PLI 修正保留，前端没有改动。

同一组 360 帧 4K SMPTE 样本，bitrate=12000：旧 30fps 预算产生 24.11Mbps，
60fps 预算产生 11.51Mbps；周期性关键帧约 86KB→66KB。软件生成测试图耗时约
30 秒，不能把这个过程当成真实采集帧率测量。

新插件安装在 `/usr/local/lib/vim4-kvm/gstreamer-1.0`，通过 nanokvm 的
`encoder.conf` drop-in 选择；原系统插件仍在原路径。原版应用更新包不包含该
平台依赖，未来系统镜像需执行新仓库的构建与 `install-vim4.sh`。

NanoKVM 新增可选 `VIM4_RTP_PACKET_SIZE`（1000–1400），默认/无效值仍是 1200。
本机验证 eth0 MTU=1500，通过 `rtp-lan.conf` 持久启用 1400。数值是 packetizer
预算，不包含后加的 RTP 扩展、SRTP、UDP/IP 开销；未知/VPN 路径应删除该 drop-in
并重启，恢复默认。通用安装器不会自动启用局域网选项。

Mac HDMI 上显示滚动文字/色块动画，Chrome headless 每轮测量约 20 秒：

- 旧预算/1200：24.51Mbps、59.99fps、52192 包，平均组帧 1.41ms。
- 新预算/1200：12.31Mbps、59.99fps、26499 包，平均组帧 0.63ms。
- 新预算/1400：12.32Mbps、59.99fps、22822 包，平均组帧 0.54ms；复测
  12.42Mbps、59.99fps。各轮网络丢包、解码丢帧、freeze 均为 0。
- 解码帧间隔标准差约 6.08ms→3.42ms，1400 两轮为 3.54/3.74ms。
  呈现回调采到的解码耗时 p99 从 5.6ms 降到 4.6ms。
- 浏览器呈现最大间隔仍有波动：旧 49.9ms，新预算 35.3ms，1400 两轮为
  33.9/47.5ms。不能声称大包已经稳定消除显示卡顿，也未测玻璃到玻璃延迟。
- 原版 FPS 切换 30→自动：5 秒分别解码 150、300 帧，最终恢复自动。

VIM4 Go 全套测试、默认 Go 全套测试、两种后端编译通过；改分包选项后再次通过
WebRTC 测试和两种后端编译。没有使用 strace/pprof 参与对比，没有开启严格跳帧
码控、固定 QP、帧内刷新或批量发送。原有未提交优化没有合并进本轮提交。
原始浏览器统计保存在 gitignored `logs/vim4-{before-rate,after-rate,after-1400,
after-1400-repeat}.json`。`/tmp/NanoKVM-Server` 未改，构建使用独立文件名。
## 组件包部署闭环验证（2026-10-13）

- 主仓库 e72154b 的干净源码构建四组件包 1.0.3+vim4.20261012.1；隔离构建
  包含主仓库 17 项测试、部署辅助工具 7 项测试、两种 Go 目标及前端构建。
  包校验、ARM64 动态依赖、sudoers 和配置保留验证通过。
- 上传现有 Ubuntu 板子增量安装，未刷 eMMC、未替换内核或重新协商 USB-PD。
  手工服务和编码插件路径迁移到包管理路径；保留 rtp-lan.conf 的 1400 参数。
- 发现旧 sudoers 仍引用 /usr/local/libexec，修复为包内 /usr/libexec；发现开机
  wants 链接仍指向已迁移的 /etc 服务，安装工具使用 reenable --force 重建链接。
- board.py check 通过，USB UDC 为 configured；应用进程映射确认实际加载
  /usr/lib/vim4-kvm 下编码插件及系统目录中的 vfmcap。特权 ssh-get 查询成功。
- Chrome 无头浏览器采样 15.006 秒，3840×2160，解码 901 帧（60.04 fps），
  framesDropped/packetsLost 增量均为 0。当前场景的冒烟结果不能代表高运动负载、
  音频、HID 实际输入或端到端延迟；本轮未重启验证。
- 构建/包验证日志在 build/deploy-{build,verify}-20261012.1.log，视频数据在
  logs/deploy-video-smoke.json。安装与浏览器测试已固化为 install-components.sh
  和 video-smoke.mjs，入口见 docs/board-tools.md。
## 无人值守部署（2026-10-13）

- `board.py enroll` 在开发板安装 /etc/sudoers.d/vim4-dev-nopasswd（khadas 免密 sudo），
  不进入组件包与镜像；`sudo -n true` 验证通过。Ubuntu 密码未改。
- 首次 enroll 失败的原因是 board.py 的第一个 ssh 子进程继承 stdin、吞掉了经管道传入的
  密码，sudo 收到空行。子进程改为不继承 stdin 后通过；不是密码错误。
- 随后 `board.py deploy --exclusive --packages build/packages/1.0.3+vim4.20261012.1`
  全程无密码：上传、install-components.sh 校验/迁移/重建启用链接、重启 nanokvm、
  版本核对与 check 均通过，UDC configured。
- video-smoke.mjs 15.005 秒，3840×2160，解码 900 帧（59.98 fps），丢帧/丢包 0。
  同版本重装，不代表新版本或运动场景、HID、音频、延迟通过；本轮未重启整机。
- 同日 `board.py verify` 首次实机运行：hid PASS（hidg1 绝对坐标移动 Mac 光标并恢复），
  audio PASS（1 秒 48000 帧，峰值 0，信源静音，未验证音频内容），video PASS
  （3840×2160 60.0 fps，丢帧/丢包 0）。日志 logs/board-20261013-122034-b9aa0b/。
- 同日 `board.py provision` 实机验证：在当前板子用临时 SSH 密钥模拟新镜像，公钥登录
  被拒后以默认密码登录一次，写入公钥，随后公钥登录与免密 sudo 均通过；临时密钥与
  SSH 配置已清理。未经实际刷机，flash 后自动 provision 只由离线测试覆盖。

## 保持画质的低延迟验证（2026-10-13）

- 部署组件 1.0.3+vim4.20261013.5；增加默认关闭的采集/发送分段计时，未改前端。
  ARM64 构建、两种 Go 目标、前端、包校验通过；工作区 34 项测试通过。
- 4K60、12000 Kbps、GOP 120、原 QP 不变。在 MTU1500 的当前直连局域网启用
  已有 rtp-lan.conf（RTP1400）；顺序对照 I 帧发送中位数 9.289→7.807ms。
  整体延迟中位数没有因此下降，改善集中在尾部。完整帧低延迟模式保持 0x3。
- 关闭诊断后运动场景 20 秒复测：59.99fps，中位延迟 66.79ms、p99 72.53ms；
  浏览器丢帧/丢包/冻结为 0，172 个一致性样本通过，内核累计丢帧仍为 0。
  首轮时钟误差超限，已拒绝其延迟结果。测量端点是源绘制到 Chrome 合成器，
  不是光学延迟、键鼠响应或 Safari。详见 [测量文档](latency.md)。
- 服务与包完整性检查通过；临时诊断配置及本轮板上日志清理完毕。1080p 仅做过
  诊断，已恢复 3840×2160。未改变降帧策略，未降低码率或启用降画质参数。

## 键鼠输入延迟与行为（2026-10-13）

- 通过原前端 → WebSocket → USB HID → Mac 原生测试窗口完成两轮测试。
  键盘发送到原生事件中位约 4ms，绝对鼠标移动约 2.8ms，不含视频返回延迟。
- 长按方向键由被控 Mac 在约 500ms 后、每约 84ms 重复一次，松开和合成 blur
  均释放；重复 keydown 未造成额外 HID 按下/释放。未测试所有输入法和断网场景。
- 复现 Mac 自然滚动造成方向反转；原菜单“鼠标 → 滚动方向 → 向下”即可匹配。
  只改测试浏览器偏好，没有修改用户常用浏览器、系统滚动设置或生产前端。
- 固化 input-target.swift、input-check.mjs、input-summary.py；参数化脚本再次实机
  通过，目标窗口退出恢复桌面。测试方法与边界见 [输入验证](input-latency.md)。

## HDMI 静音修复及重新打包验证（2026-10-13）

- 确认默认 TDM-B 输入选了外部引脚，HDMI 有音频包但录音和 WebRTC 都静音。
  HDMI 服务 ExecStartPre 在 ALSA restore 后设置 hdmirx；板级包依赖 alsa-utils。
  包与镜像校验检查路由及先后顺序，实测旧 .6 包被新校验拒绝。
- 修复 VIM4 音频采集和发送重复等待 ticker 的问题；单轮 6 秒稳态从约 42–46
  包/秒改善到约 50 包/秒，缺音补偿增量为 0。后续复测仍有少量补偿，不能作为
  长期零缺音保证。原界面的音量默认静音行为未改。
- 最终组件 1.0.3+vim4.20261013.9 来源全为干净提交，配方 0cd08f1，应用 d175ecd。
  38 项工作区测试、两种 Go 目标、前端、依赖及包校验通过，四组件上板通过。
- 故意把输入重置为 tdmin_b，再整机重启；boot ID 已变化，NanoKVM/HDMI 服务
  active，路由自动成为 hdmirx（值 6）。包完整性和服务检查通过。
- 重启后原音量菜单打开播放，6.007 秒非静音音频测试收到约 47.94 包/秒，
  丢包 0，补偿 3924 个采样、7 次事件。它证明声音恢复，不证明无间断播放。
  视频随后单独采样 10 秒，3840×2160、601 帧（60.08fps），丢帧/丢包 0。
- 官方 Ubuntu 基础镜像加入同一 .9 组件重新组装，通过只读校验、文件系统检查、
  音频启动顺序和 amixer 依赖检查，导出到
  build/images/vim4-kvm-ubuntu-1.0.3-audio9/（约 692MiB，附 SHA256SUMS）。
  没有擦写板子；此候选镜像的全新刷机启动验收仍未执行。
- 证据：build/audio-final-{build,verify,image-assemble,image-export}.log，
  logs/audio-final-{deploy,reboot,health,state}.log、audio-final-browser.json、
  audio-final-video.json。功能缺项纠正见 [功能状态](feature-status.md)。
