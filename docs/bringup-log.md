# 上板记录

## 2026-10-14：MJPEG 单帧耗时与 NanoKVM 分辨率菜单

在 `.20` 的编码路径上增加临时计时探针（只从 /tmp 加载，不安装探针插件），
保持 4K60 输入、Q80、666MHz 默认编码时钟和全屏运动网格。连续输入 300 帧，
队列允许丢弃积压帧，去掉起始 10 个输出后统计 238 个编码输出，平均耗时如下：
DMA 导入 0.016ms、命令提交 0.163ms、poll 等待完成 18.792ms、输出 ioctl
0.206ms、输出复制 0.803ms、释放导入 0.013ms。证据：
logs/mjpeg-hardware/profile-split.log、profile-motion-split.jsonl。

poll 包含硬件运行与中断/调度等待，不是纯硅片时延；但远大于 DMA/提交开销，
不能把每帧约 19ms 的等待归因于网页限帧。当前路径即使忽略其他开销也仅约 53fps，
尚未证明能稳定 4K60。驱动 jpeg_enc_clk_enable 对 T7 固定设置 666666666Hz，
其 clock_level 参数不改变这个分支；没有超频或修改内核。测试结束恢复 NanoKVM。

NanoKVM e3dbe78 删除采集分辨率菜单遗留的 MJPEG 10fps 显示上限，按配置 FPS
显示（自动时为 60），保留原样式及实际帧率说明，并修正流设置 API 文档。
前端需显式使用 VITE_PLATFORM=vim4；首次 `.21` 漏带参数，实机检查发现通用菜单，
随后重新构建 `.22`。通用构建检查不能替代 VIM4 菜单实机验证。
`.22` 组件校验和部署通过，Chrome 实机打开采集分辨率菜单及刷新后，三个选项均
显示“最高 60 FPS”，保存设置仍为 4K、60fps、Q80、30000kbps。证据：
logs/mjpeg-hardware/nano-resolution-ui.log、nano-resolution.png、
verify-resolution-final.log、deploy-resolution-final.log。保留当前 NanoKVM 选择、
disk.img 挂载和 HDMI 服务运行实例。

## 2026-10-14：MJPEG 硬件编码与 4K 运动画面吞吐

原 NanoKVM / One-KVM 的 VIM4 路径使用软件 jpegenc 并主动限制到 10fps。
新增 vim4jpegenc，通过 /dev/jpegenc 编码 NV12/NV21 DMA 输入，质量支持 1–100。
厂商 amljpegenc 直接 DMA 输入实测只输出 4 帧后停滞：NEW_CMD 路径未归还
导入的采集缓冲。新插件使用 CONFIG_DMA_INPUT / RELEASE_DMA_INPUT 管理逐帧
导入；异常时关闭硬件后释放输入。没有改内核或超频，缺少新插件时仍回退软件 10fps。
NanoKVM 取消原应用 30Hz 轮询限制；One-KVM 在缩放后使用单帧队列重叠缩放与编码，
状态接口按实际帧数计量，并沿用公共接口的百分之一帧存储单位。

HDMI 输入 3840×2160、约 60Hz，以 tools/latency-source.swift 的 --motion
模式生成全屏运动网格，编码器保持原 666MHz。每组 240 帧，统计剔除起始 10 帧：

| 输出 / JPEG 质量 | 板端编码 fps | 编码数据 Mbps |
|---|---:|---:|
| 2160p / 50 | 51.17 | 393.49 |
| 2160p / 80 | 51.22 | 582.93 |
| 2160p / 100 | 47.19 | 1290.96 |
| 4K 缩至 1080p / 80 | 40.78 | 188.33 |
| 4K 缩至 720p / 80 | 43.62 | 110.18 |
| 再次开启 2160p / 80 | 51.21 | 583.57 |

各组首尾 JPEG 均成功解码，重复关闭、开启通过。缩小分辨率包含 GE2D 成本，
不能用原生小分辨率性能解释这些结果；51fps 是当前路径实测，非芯片理论上限。
Q100 的数据量超过千兆网络容量，不能承诺该质量下的完整帧率交付。

`.19` 实机 Chrome 在相同 4K/Q80 运动画面下，One-KVM 初次连接 / 刷新收到
50.84 / 50.75fps，约 579Mbps；NanoKVM 为 42.60 / 39.59fps，约 488 / 454Mbps。
此处统计 HTTP 收齐的完整 JPEG 帧，不是显示器实际呈现帧数。另用真实 One-KVM
网页验证 MJPEG 图像尺寸为 3840×2160。首次部署发现状态显示单位不符，将真实
约 51fps 显示为 0.51fps，后续修正不影响编码或收帧路径。

最终 `.20` 完整包校验及部署通过，Chrome 再次连接 / 刷新收到 50.90 / 50.79fps，
状态接口分别为 50.77 / 50.64fps，确认显示单位修复。记录见
browser-one-final.jsonl、verify-fps.log、deploy-fps.log；编码器固定 a99edf0，
NanoKVM c6ad206、One-KVM 84172cdf，部署根源码固定 7463ca3。

构建验证：NanoKVM VIM4 Go 测试、One-KVM 561 项 Rust 测试、两套前端构建、
根仓库 42 项测试及组件包隔离升级校验通过。插件以 -Wall -Wextra -Werror 构建。
One-KVM 二进制保留此前 `.17` 已部署的 VNC Tight JPEG 兼容改动，包内 sources.json
记录其精确未提交补丁，未改动原工作树的该文件。JetKVM 不提供 MJPEG，此次未新增。

证据位于 logs/mjpeg-hardware/：motion-final.jsonl、browser-one.jsonl、
browser-nano.jsonl、one-ui-smoke.log、one-fps-build.log、nano-final-build.log。
测试后恢复 One-KVM 选择及原 MJPEG 模式；USB disk.img 挂载保留，HDMI 服务未重启。

## 2026-10-14：JetKVM 码率控件部署

JetKVM `9faf1c5` 将码率预设、0.1 Mbps 滑块和精确 kbps 输入合并，
采用原生下拉框、滑块轨道和保存按钮。浏览器回归覆盖同步、显式保存、
刷新恢复、保存失败回退、非法边界和保存按钮文字。干净快照前端构建、
ARM64 构建及内部 Go 测试通过，最终 `.16` 七组件包校验与部署通过。

实机 Chrome 将 12 Mbps 改为 17.6 Mbps，保存并刷新确认，再恢复 12 Mbps；
配置文件确认 factor=1。最终版 3840×2160 视频采样 10 秒约 60.06fps，
零解码丢帧、零 RTP 丢包。保留当前 JetKVM 选择，HDMI 服务未重启。
`.15` 截图发现旧控件以 children 传递按钮标签而组件只读取 text，已在
`.16` 修正并补充可见标签检查。未测试长期运动场景或端到端延迟。
证据：`logs/jet-bitrate-final-{build,package,verify,deploy,browser}.log`、
`logs/jet-bitrate-deployed.png`。

## 2026-10-14：NanoKVM 码率菜单样式修正

NanoKVM `a0c9574` 清除新增档位按钮的浏览器默认背景、边框与字体，
继承原菜单样式，滑块区域缩至 180px。VIM4 前端构建和码率浏览器回归通过。
完整 `.14` 包校验及部署通过；Chrome 实机检查确认透明按钮背景、无边框、
继承菜单文字颜色和字体，深色主题截图符合原菜单风格，视频正常播放。
当前设备码率为用户设置的 30 Mbps，刷新后恢复；测试未写入码率。
证据：`logs/nano-style-{release-build,package,verify,deploy,browser}.log`、
`logs/nano-style-deployed.png`。

## 2026-10-14：NanoKVM 码率滑块部署

NanoKVM `d639e8f` 增加 1–60 Mbps 快捷档与 0.1 Mbps 步进滑块，
拖动结束提交，刷新从设备设置恢复自定义值。两种前端构建、浏览器模拟 API
回归（拖动只在释放时保存、刷新恢复、保存失败回滚）通过。

干净快照重新构建 NanoKVM 前端，原生二进制复用 `.12` 验证产物，生成
`2.5.1+vim4.20261014.13` 七组件包；隔离包验证与部署检查通过。
实机 Chrome 确认滑块和快捷档存在，刷新后恢复原来的 50 Mbps；未修改用户
视频参数，保持 NanoKVM 为当前应用，HDMI 服务 InvocationID 未变化。
部署后 H.264 WebRTC 3840×2160 采样 10 秒：600 帧、59.97fps，
零解码丢帧、零 RTP 丢包。此为播放冒烟检查，不代表运动场景或端到端延迟。
证据：`logs/nano-slider-{release-build,package,verify,deploy,browser,video}.log`、
`logs/nano-slider-deployed.png`。

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

## 补齐原 NanoKVM 功能缺项（2026-10-13）

- 最终组件 1.0.3+vim4.20261013.18 来自干净提交（应用 6e05134、编码插件
  7f34fb3、主仓库 492fa09；清单固定提交尚未更新）。开发包 .10–.17 带脏标记，
  仅用于逐项上板。board.py verify 的 hid/audio/video 全部 PASS。
- 防休眠：相对、绝对两种模式实际移动 Mac 光标；重启 NanoKVM 后保持开启，
  关闭后删除配置，不再移动。
- H.264 Direct、H.265 WebRTC/Direct：4K60 静态桌面，各模式解码约 60fps、
  丢帧 0；H.265 协商 video/H265，携带 NACK/PLI/RTX。最后一个查看端离开后释放
  编码器。Direct 依赖 WebCodecs，Chrome 只在安全上下文提供，HTTP 下需 HTTPS。
- 自定义 EDID：hdmirx edid_with_port + EDID_UPDATE_WITH_PORT ioctl 写入 port B；
  Mac 识别到自定义显示器名，并能在 4K60/1080P60 预设间切换。tvserver 开机写入
  厂商 EDID 后由 HDMI 服务恢复所选 EDID，整机重启验证通过；修改采集分辨率重启
  HDMI 服务不会再次拉低 HPD。
- MJPEG/Direct 音频：增加纯音频 WebRTC 会话。复测发现 GetStreamType 与读帧共用
  互斥锁，10fps MJPEG 只收到 3 包/秒；改为原子读取后，四种模式均 50 包/秒，
  补偿 0，能收到 440Hz 测试音。H.264 WebRTC 在低帧率设置下也受益于此修复。
- CBR/VBR：厂商 strict_rc_window 实测会跳过大量帧，也不能把码率压在目标值，
  因此不采用（logs/rc-strict-window-20261013.txt）。VBR 改用 qp-max=36 上限。
  运动画面、3000 Kbps 目标时，浏览器端 CBR 3.99 Mbps、VBR 10.23 Mbps，均为
  60fps 且丢帧 0（logs/rc-browser-20261013.txt）。
- 快照：/api/stream/snapshot 请求 IDR 后软件解码，或直接采集；直播 H.264 期间
  取快照用时 0.25–0.77s，查看端保持 60fps、丢帧 0。
- Tailscale：经官方签名 apt 源安装约 20 秒，状态 notLogin，能取得登录链接，
  停止/启动/卸载正常。没有账号授权，未验证组网。测试后已 purge，恢复原状。
- AI 助手：python3-venv + 应用私有 venv 安装依赖；页面、令牌鉴权、socket、
  桌面预览（快照）正常。经助手函数验证绝对定位到 (0.25,0.25)，相对移动正常。
  未提供模型 API Key，未执行推理任务。
- USB 麦克风：UAC2 仅提供主机输入（48kHz 双声道），开启时替换 NCM；可与虚拟介质
  同时存在（HID×3+存储+UAC2 已枚举，HID 正常）。Chrome 模拟麦克风经原按钮开启后，
  NanoKVM 启动 aplay 并收到 PCM；关闭后恢复 NCM。终端没有 macOS 麦克风权限，
  未验证主机实际录到声音（tools/uac-record-level.swift 待授权后复测）。
- 内核崩溃：USB 功能重新绑定后关闭仍注册在 epoll 中的 /dev/hidg*，触发
  remove_wait_queue list_del corruption（logs/uart-mic-crash.log）。5.15
  f_hid 的 hidg_bind 会重新初始化等待队列。应用改为重新枚举期间关闭 HID 文件，
  复现序列不再崩溃；内核侧根因修复待处理，虚拟介质切换此前也存在同样风险。
- 崩溃损坏：根分区 data=writeback，panic 前两分钟安装的 6 个 NanoKVM sudoers
  文件被清零，特权接口失效。dpkg --verify 确认仅这 6 个 conffile 受影响；
  经授权按包内容恢复并 visudo 校验，此后部署均 sync。

## HID 生命周期与部署可靠性（2026-10-13）

- 官方 Khadas fork vim4-kvm/linux 的 dbcef7c1f 把等待队列初始化移到实例分配，
  b86c7e5bd 为每次绑定分配独立 cdev，旧描述符关闭后才释放旧设备；补齐分配及
  注册失败清理。原作者保留，应用 Reenumerate 保护保留。CONFIG_USB_F_HID=y，
  修复必须通过完整 Image 与重启生效。
- 第一轮只含等待队列修复，保持 epoll 注册跨 UDC bind 的测试仍触发
  list_del corruption，SSH 失联，串口只捕获到错误开头，需要 RESET 恢复。
  因此单项补丁与候选 reliability19 均不能作为完整修复交付。恢复后所检查的
  应用、板级和内核包未报告文件校验差异；不能据此证明所有未纳管文件都未损坏。
- 最终内核 b86c7e5bd 启动 ID 79719ee3-c0ec-4495-a097-0991d465ee6f，Image SHA256
  e689f0b003375663d19643fbf3dcc6c54185966d3f4bc7ebae38dd24a6fdfdd1。
  三个 HID 文件在 epoll 中保持打开，重新绑定后注销/关闭，连续 20 轮通过。
  原查看页面在线时再做 3 轮麦克风→只读 ISO→弹出→NCM，均通过，启动 ID 未变化，
  未发现新的 list corruption/BUG/Oops/panic。没有验证所有并发读写与拔线场景。
- 原根分区为 data=writeback、commit=600。rootfs-policy 仅修改 Default 启动行，
  明确追加 rootflags=data=ordered；根分区和 /boot 的 fstab commit=5。
  Stock 行未变。重启后的 findmnt 和 ext4 启动日志确认生效；这不保证任意断电无损。
- 在线发布改为封装组件 deb，消除 /usr/local/libexec 与 /usr/libexec 不一致，
  统一依赖、服务路径、配置保留和安装检查。更新前模拟 APT，需平台升级则拒绝；
  成功后核对辅助程序与 sudoers、visudo、sync，再安排应用重启。所有组件 postinst
  增加 sync，部署在建立服务链接后再次 sync。空 sudoers 的组件配置测试明确失败。
- 干净构建 .19：40 项工作区测试、27 项部署测试、两种 Go 目标、前端及包检查通过。
  原手动更新 API 上传同一组件的封装包，任务 succeeded，NanoKVM PID 从 1299
  变为 1534，安装文件校验通过。本轮验证了同版本重装，尚非全新刷机后的跨版本升级。
- 最终板子保持用户的 1080p EDID：board.py verify 键鼠/音频/视频 PASS。
  10 秒视频 600 帧、59.95fps、丢帧/丢包 0；定向测试音录音峰值 3277。
  Chrome 音频 6.005 秒约 49.96 包/秒，非零能量、丢包及补偿 0。
- 新候选 reliability19b 使用 .19 组件及完整 HID 内核修复；结构、文件系统、
  启动策略、依赖、sudoers、音频路由校验通过。没有擦写板子，也没有完成该候选
  的全新刷机启动验证。版本清单已更新；子仓库提交需先于主仓库清单推送。
- 证据：build/reliability-{build,verify,final-image,export}.log，
  logs/reliability-{hid2-rebind,hid2-uart,usb-switch,final-verify}.log，
  reliability-update-{inspect,confirm,result}.json、reliability-browser-audio.json。

## 采集分辨率菜单部署（2026-10-13）

- 干净构建并校验 `1.0.3+vim4.20261013.20`，应用提交 `a7c0630`；通过
  `board.py deploy --exclusive` 安装四组件，服务检查通过，没有重启内核。
- Chrome 打开板上实际页面，确认菜单显示分辨率、最高 FPS 和采集输出说明，
  当前 3840×2160 配置被勾选；没有切换分辨率或 EDID。
- 当前信号实际输出 1920×1080；H.264 WebRTC 采样 10.007 秒解码 600 帧，
  59.96fps，丢帧/丢包均为 0。菜单配置值不代表实际输入尺寸或实时帧率。
- 证据：`logs/package-20261013-20.log`、`logs/verify-package-20261013-20.log`、
  `logs/deploy-20261013-20.log`、`logs/video-20261013-20.json`、
  `logs/deployed-resolution-menu-20.png`。本轮未重新测试音频、HID 或端到端延迟。

- 后续设置页改为 EDID 相同的标题/说明加 Select 布局，应用提交 `da6150a`，
  干净构建、校验并部署 `1.0.3+vim4.20261013.21`。本地浏览器模拟接口验证
  下拉框与快捷菜单双向同步、保存失败保留旧值并提示错误；板上 Chrome 确认
  下拉框显示三档尺寸及最高 60 FPS，视频正常显示，没有切换实际采集设置。
  部署服务检查通过，截图 `logs/deployed-resolution-settings-21.png`；构建、
  包校验和部署日志分别为 `logs/{package,verify-package,deploy}-20261013-21.log`。

## H.265 默认开放（2026-10-13）

- H.265 后端已经实现，但两个前端入口仍依赖上游 `h265` Cookie，原冒烟脚本
  注入该 Cookie 掩盖了普通用户入口的问题。VIM4 现在默认开放 H.265，保留
  浏览器能力检测；快捷菜单逐模式检查能力，避免 HTTP 下误启 Direct。
  非 VIM4 版本保留原启用流程，冒烟脚本移除 Cookie 注入。
- 应用 `60afb9e` 干净构建、包校验并部署 `.22`；服务检查通过。
  新 Chrome 会话通过实际设置下拉框选择 H.265 WebRTC，收到 H.265 解码帧，
  前后均没有 `h265` Cookie；快捷菜单入口同样可用。
- 当前 3840×2160 信号：H.265 WebRTC 10.008 秒解码 601 帧（60.05fps），
  丢帧、丢包均为 0。H.265 Direct 画布显示 3840×2160，10.002 秒收到
  600 条帧消息；这不是 Direct 渲染丢帧计数或端到端延迟测量。
- Direct 测试使用 Chrome 的指定源安全上下文开关；常规访问需 HTTPS。
  本轮未测试 Safari，也未作复杂运动画面质量与延迟对比。
  证据：`logs/h265-{ui,webrtc,direct}-22.*`、`logs/deploy-20261013-22.log`。

## KVM 界面管理面板（2026-10-13）

新增 vim4-kvm/vim4-manager 仓库（本地 main，尚未推送）：Go 后端嵌入 React 前端，
以 khadas 监听 80 端口，选择开机启用 NanoKVM-Pro 或 JetKVM，并显示 HDMI、USB、
温度、内存和底层服务。特权操作只经 sudoers 限定的 /usr/libexec/vim4-manager-helper。
JetKVM 打包为 vim4-jetkvm（/opt/vim4-jetkvm，状态目录 /var/lib/jetkvm）。
之前沿用 StateDirectory=vim4-kvm，会把含 NanoKVM EDID 的 root 目录改归 khadas，已改名。
包不启用 JetKVM；install-components.sh 保留当前选中的应用，不再固定重启 nanokvm。
重刷后板上原 JetKVM 和配置已不存在，首次打开时用其 /device/setup 选择了免密码模式。

版本 1.0.3+vim4.20261013.30 由仅含已提交源码的 worktree 快照构建（另一会话的
NanoKVM-Pro 工作区未提交改动不在其中），ubuntu-build verify 通过，board.py deploy
六包一致、check 通过。证据 logs/package-30.log、logs/deploy-30.log。

- 切换到 JetKVM 约 1.4 秒：nanokvm 停止并禁用，jetkvm 占用 8080。
  Chrome 10 秒 3840×2160 约 60.0fps、丢帧 0；通过 JetKVM 网页移动指针，
  Mac 光标到 (0.235,0.300)、(0.712,0.601)，目标 (0.25,0.30)、(0.70,0.60)。
- 切回 NanoKVM 后 video-smoke 10 秒 3840×2160、60.2fps、丢帧和丢包 0。
- 重启 HDMI 采集：日志顺序为 nanokvm 停止 → HDMI 重启 → nanokvm 启动，之后
  4K 约 60fps、丢帧 0。重启 gadget 的请求被拒绝；跨站表单式 POST 返回 415。
- 选择 JetKVM 后整机重启：jetkvm、manager 及 HDMI/gadget/PD 均 active，
  UDC=configured，JetKVM 4K 约 60fps、丢帧 0。之后切回 NanoKVM 作为板子当前选择。

未覆盖：JetKVM 键盘输入、长时间运行、多浏览器同时操作面板、断电冷启动。
面板 API 无认证，仅适用于可信局域网。

## JetKVM 完整功能接入（2026-10-13）

kvm 仓库去掉 basic_kvm 限制，按能力上报接入 JetKVM 原有功能；特权操作只经
/usr/libexec/vim4-jetkvm（JSON 经 stdin，sudoers 仅此程序），功能与边界见
kvm/VIM4.md。上板为开发构建，随后以网页更新安装 1.0.3+vim4.20261013.33
（--allow-dirty 构建，其余组件仍为 .30）。测试工具 tools/jetkvm-smoke.mjs
通过页面自身的 rpc 数据通道调用接口。证据 logs/jetkvm-full/。

- H.264/H.265 1080p 与 4K 约 60fps、10 秒丢帧 0；画质系数实测重开编码器
  6000/12000kbps、60fps（静态桌面码率远低于上限，不能用码率证明画质）。
- HDMI 音频 G.722 50 包/秒；440Hz 测试音能量 0.079，静音约 1e-7。JetKVM 默认 EDID
  使 Mac 音频设备名变为 “JetKVM v1”，hdmi-audio-tone 改为可传设备名。
- EDID：JetKVM 加载配置时把空值迁移为其默认表（1080p），保留为默认；追加厂商
  4K60/1080P60 预设，4K 预设使 Mac 输出 3840×2160。空闲隐藏显示经 hdmirx debug
  拉低 HPD，无查看端时 Mac 显示器消失，有查看端时恢复 4K。
- ISO 经 HTTP 上传，CD-ROM/Disk 挂载，Mac 读出镜像内文件；弹出恢复 NCM；
  重新枚举后绝对/相对指针正常。USB 模拟关闭使设备消失，打开后恢复输入。
- 网络设置往返（mDNS 改为仅 IPv4 再恢复）、avahi 解析、Wi-Fi 扫描与测试网络
  保存/连接失败/删除；SSH 公钥写入 authorized_keys2；443 自签 HTTPS；终端为 khadas；
  诊断包含 journal；本地密码设置与删除；Tailscale 登录链接与控制服务器。
- 网页更新首次失败两处并已修复：上游 OTA 下载后写 /proc/sys/vm/drop_caches 需 root；
  vim4-jetkvm 依赖同版本平台包，单包更新必然被 APT 拒绝，改为固定下限。修复后下载、
  校验、安装、dpkg --verify、重启全部通过，重启后服务、gadget、4K 视频、音频、指针正常。
- 恢复出厂设置清除 JetKVM 配置、镜像、TLS 后重启，保留 ~/.ssh/authorized_keys。
- Ubuntu 的 tailscale 1.104 没有 `set --login-server`，控制服务器改为登录时指定。

测试结束切回 NanoKVM，并以 `vim4-edid preset VIM4-4K60` 恢复测试前的厂商 4K EDID。
板上 vim4-jetkvm 为 .33 开发包，比最终提交少“安装后删除下载包”一处改动。
未覆盖：经 URL 挂载（内核无 NBD）、真实 Wi-Fi 连接、修改当前以太网地址、真实
tailnet/MQTT、唤醒睡眠主机、长时间与复杂运动画面、HDMI 热插拔、断电冷启动。

本轮另一会话同时打包 NanoKVM。kvm 的 gstcapture 接口修改到一半时，对方
2.5.1+vim4.20261013.2 构建在 JetKVM 测试处失败（logs/nanokvm-migration-package.log）。

## NanoKVM 正式部署与 JetKVM 往返切换（2026-10-13）

六个 Ubuntu 组件完整更新到 `2.5.1+vim4.20261013.5`，保留 Ubuntu 账户、
内核与当前 NanoKVM 选择。干净构建使用 workspace `355cee7`、NanoKVM
`93d8fc0`、manager `1575c43`、JetKVM `1e469f5`；包校验覆盖校验和、ARM64
ELF/依赖、sudoers、配置保留和损坏文件拒绝。正式部署使用
`board.py deploy --exclusive --packages build/packages/2.5.1+vim4.20261013.5`。

初测发现并修复：

- manager 仅靠 systemd Conflicts 切换，旧 NanoKVM 尚未退出时 JetKVM 已启动，
  导致 8080 bind panic。助手在 select/restart 中等待另一应用停止，再启动目标；
  单元测试覆盖顺序及 stop 失败时不得启动。
- 共用来源的首页缓存会让 JetKVM 页面加载成 NanoKVM。管理器链接增加应用查询参数，
  NanoKVM 的 `/` 和 `/index.html` 返回 `Cache-Control: no-store`；上板核对通过。
- NanoKVM VIM4 不再写设备固件专用的 `/kvmapp/kvm/now_fps`，仍更新帧率 API。

此前 JetKVM 恢复出厂后仍处于初次设置状态；通过原生 setup API 按既定本地免密码
模式完成初始化。没有修改 Ubuntu 账户密码。

新增 `tools/kvm-switch-check.mjs --exclusive`，保留旧浏览器会话直到切换完成，
调用真实管理器 API，检查两个服务 active/enabled 状态并读取 Chrome WebRTC stats。
正式包结果（当前桌面场景，每段 10 秒）：

| 顺序 | 应用 | 切换到首帧 | 解码 fps | 丢帧 / 丢包 |
|---|---|---|---|---|
| 1 | NanoKVM | 2117 ms | 60.07 | 0 / 0 |
| 2 | JetKVM | 2124 ms | 59.98 | 0 / 0 |
| 3 | NanoKVM | 1888 ms | 59.97 | 0 / 0 |
| 4 | JetKVM | 1981 ms | 60.04 | 0 / 0 |
| 5 | NanoKVM | 1950 ms | 60.08 | 0 / 0 |

全部为 3840×2160。最终 `board.py verify`：USB 绝对指针真实移动 Mac 光标并恢复；
ALSA 一秒取得 48000 帧，但峰值 0，仅证明采样运行，不证明声音可听；H.264 视频
60.07fps、零丢帧/丢包。服务无 failed 项，UDC configured，dpkg audit 无输出。
新版本切换日志未见 bind panic 或 now_fps 错误；关闭测试浏览器时仍有上游记录的
WebSocket close 1001，不影响下一次连接。

证据：`logs/nanokvm-switch-{package,verify,deploy}.log`、
`logs/nanokvm-jetkvm-switch-packaged.log`、`logs/nanokvm-switch-final-verify.log`、
`logs/nanokvm-switch-journal-installed.log`。未测端到端输入延迟、键盘、长时间复杂运动、
重启及新镜像刷机；当前结果不能代替这些验证。最终 NanoKVM active/enabled，
JetKVM inactive/disabled，通过管理器 `http://192.168.50.210/` 可切换。

## NanoKVM 终端、镜像上传与可写 U 盘（2026-10-13）

最终应用为 `2.5.1+vim4.20261013.8`（NanoKVM `b6bc786`），其他组件保持 `.7`。
管理器工作树有另一项任务的未提交修改，因此 `.8` 在独立目录按清单构建，只更新应用包。
构建、默认/VIM4 后端测试与构建、两种前端构建、sudoers/配置保留/包校验均通过。
新增 USB helper 的首次创建失败清理、已有数据不重建、符号链接拒绝测试；Linux 容器
内 media helper 7 项测试通过。此前删除 Smart Assistant 的更新也已部署并核对旧目录消失。

- 终端优先查找 Bash，不存在时使用 `/bin/sh -l`；真实网页 WebSocket 回读
  `BASH_VERSION=5.2.21(1)-release`。未在板子上移除 Bash 测 fallback。
- 上传失败源于应用无权创建 `/run/nanokvm-transfer-in-progress`。curl 的早期响应
  显示 permission denied，Chrome 的原生 File/FormData 请求表现为 Failed to fetch。
  VIM4 使用 systemd `RuntimeDirectory=vim4-nanokvm`、0700/khadas 和专用传输锁；
  上游平台保留原路径。前端文件选择与拖放同时接受 ISO/IMG。
- Chrome 上传 Ventoy 1.1.18 LiveCD（约 186 MiB）成功，板上 SHA-256 为
  `ee3917bd5a9973c0b2f8f3ef85048bf68ae089ec88f5561ad78b6ad308b51ab5`，与官方及本机一致。
  CD-ROM 模式在 Mac 自动挂载 VentoyLiveCD，读取 EFI/boot/bootx64.efi 成功。
  Mass Storage 模式被识别为 196 MB USB 磁盘，但 Mac 未能挂载其中的 0xEF 分区；
  不把枚举通过等同于这个混合 ISO 在磁盘模式下可读，也未测试启动 Ventoy。
- 设置里的虚拟 U 盘开关原先返回 unsupported，现使用独立的
  `/var/lib/vim4-kvm/usb/disk.img`，首次创建 512 MiB FAT32，后续不重新格式化。
  不导出 Ubuntu 根分区，也不与镜像上传目录共用文件系统；它与镜像挂载共用一个 LUN。
  `/var/lib/vim4-kvm/usb/enabled` 保存开启意图，应用启动前恢复；普通应用重启时若已挂载
  则不重新枚举 USB。挂载其他镜像/弹出会清除 U 盘开启意图，麦克风切换保留它。
- Mac 实际写入 29 KiB 测试文件，弹出、关闭/开启 U 盘后回读哈希一致；重启 NanoKVM
  服务后仍可读。测试文件已删除，U 盘已关闭、NCM 恢复；Ventoy ISO 保留供用户使用。
  开启时 USB 网卡让出端点，HID 保留。此轮未测试整板冷启动或突然断电时文件系统恢复。

最终 `board.py verify`：USB 绝对指针通过；4K H.264 10 秒 59.98fps、零丢帧/丢包；
音频取得 48000 帧但峰值为零，不能证明可听声音。无 failed units，dpkg audit 无输出，
测试窗口内内核日志未见 panic/Oops。证据位于 `logs/media-tests/`。
新增 `tools/media-upload-check.mjs` 复测浏览器原生上传及终端 Bash，它不会自动删除上传镜像。

## 虚拟显示器退出后 HDMI 桌面未恢复（2026-10-13）

用户确认已退出虚拟屏；Mac 的显示器枚举仍只有 1920×1080 虚拟显示器，
没有 AML TV。VIM4 此时报告 3840×2160、约 59.98Hz、FSM_SIG_READY、
no_signal=0、avmute_skip=0、ECC 计数为零；vfm_cap 接收与交付计数继续增长。
这些状态不能证明 HDMI 像素仍代表当前桌面。

没有更换 EDID 内容，也没有重启 NanoKVM、tvserver 或 HDMI 服务：仅对
/dev/hdmirx0 调用 HDMI_IOC_EDID_UPDATE_WITH_PORT（端口参数 2，即 RX port 1），
Mac 随后重新枚举 AML TV 4K60。该 ioctl 同时触发 HPD 和 RX 状态机重启，
所以它有效不能单独证明故障只在发送端或接收端。

恢复后在物理 HDMI 桌面绘制运动标记，Chrome 从实际解码像素读出 109 个有效标记，
无无效标记；12 秒测量约 59.98fps、framesDropped=0、packetsLost=0、freezeCount=0。
这是内容更新的证据，不只是收包速率。原始记录在 logs/hdmi-recovery/。

用户再次进入并退出虚拟屏后复现。持续内核日志没有记录到这次进出过程的 RX
失锁/重锁，退出后接收与采集状态仍正常，Mac 又只枚举虚拟显示器。
再次执行相同 ioctl 恢复连接。尚未找到板端可靠的自动触发条件；没有部署
周期热插拔或静止像素看门狗，不能宣称自动恢复已修复。

## HDR 输入映射到 SDR（2026-10-14）

Mac 开启 HDR 后，RX 报告 `HDR10-GAMMA_ST2084`、3840×2160 60Hz YUV420 10bit。
厂商 4K60 EDID 含 HDR 静态元数据（SDR/ST2084/HLG）与 HDR10+ 块。
原驱动只对 vdin1 回写调用 HDR 核，vdin0 以 8bit 采集 PQ 信号：
同一 Mac 设置界面 YMAX 151、YAVG 135、SATAVG 0.69，画面发灰。

vdin0 HDR2 核寄存器（0x1280 起）复位值与 vdin1 相同（CTRL 0xd05f）。
以临时模块调用 `hdr_set(VDIN0_HDR, HDR_SDR)` 后 CTRL 变为 0xe05e，
采集结果 YMAX 201、YAVG 158、SATAVG 2.71，颜色恢复；vfm_cap 60fps、零丢帧。

common_drivers 改为 T7 vdin0 在 HDMI 输入时按 hdr10p/vdin_hdr_flag/EOTF 选择
HDR_SDR、HLG_SDR 或直通，只替换 aml_media.ko 后重启（旧模块备份在
`/var/lib/vim4-kvm/aml_media.ko.pre-vdin0-hdr`）。开机 HDR 状态下自动映射；
用户开关 HDR 4 轮，每次 2–3 秒内 `vdin_set_hdr vdin0 fmt:0/1` 跟随，
SDR 时 CTRL 0x1c040（核关闭），无 Oops。HDR 帧 YMAX 201、SATAVG 约 2.77；
SDR 帧 YMAX 235、YAVG 212、SATAVG 3.21，与正常 SDR 一致。

未测：HLG 源、HDR10+ 源、4:4:4/RGB HDR 输入、浏览器端到端主观画质和延迟。
HDR 映射后的白场 201 低于 SDR 235，属于 macOS HDR 模式下界面白低于峰值，
未调色调映射参数。

厂商 HDR→SDR 增益表按 HDR2 OOTF 149 点（线性，满刻度 10000 尼特，增益 64 为 1 倍，
输出满刻度为 SDR 白）推算，等效于 400 尼特映射为 SDR 白。整体乘 1.0/1.15/1.3/1.5
实测 YMAX 201/214/225/235，用该模型拟合得 macOS 桌面白约 284 尼特（与 8bit 读数
151 按 PQ 反算的 285 一致）。hdmi-setup.sh 改为按 HDR_SDR_WHITE=284、
HDR_SDR_PEAK=1000 生成曲线（90% 以下线性，扩展 Reinhard 肩部）；模型预测桌面白
229.9，重启 HDMI 服务后实测 YMAX 230、YAVG 183、SATAVG 3.03。
旧脚本备份于 `/var/lib/vim4-kvm/hdmi-setup.sh.pre-hdr-curve`。高光层次只在模型中检查，
尚未用 HDR 视频或测试图主观验证。

上面的 YMAX 230 取自设置面板里的 HDR 壁纸缩略图，不是桌面白，校准有误。
改用 Mac 上 17 级 sRGB 灰阶窗口（0–255 步进 16）测量：284 尼特曲线下 HDR 模式读数为
16,33,43,54,64,75,86,98,109,120,132,144,155,167,179,191,202，白块只有 202，
暗部偏亮。拟合得 macOS 在 HDR 下把 SDR 白放在 199 尼特、以 sRGB 解码（残差 0.27 码），
厂商 SDR 编码表为 gamma 2.2。默认改为 HDR_SDR_WHITE=203、拐点 95%、
编码 sRGB 后实测 16,30,43,57,70,84,97,112,125,139,152,166,179,193,207,220,231，
与理想 SDR 值相差不超过 1 码，白块 231。

vdin0 attr 新增 `reload_hdr`，运行中按当前表重新调用 hdr_set；vim4-manager 预览
接口每次调用后立即可见，HDMI 服务未重启、vfm_cap 零丢帧。SDR 白扫描（灰阶窗口外的
设置界面整帧 YAVG）：350→168、280→184、203→210、180→215、160→217、157→217，
120 反而降到 209：增益 10000×64/120=5333 超出 12 位增益寄存器（厂商各表最大 4095）
后回绕。SDR 白下限因此定为 160，曲线工具同时把增益钳在 4095。

## HDR 审查修复与部署（2026-10-14）

主仓库 `c84939d` 修复 systemd 重复 EnvironmentFile 导致音频包校验器抛出
DuplicateOptionError；曲线工具严格拒绝非十进制参数，不再吞掉重载写入失败。
新增曲线硬件边界测试，验证 149 点、12 位范围、单调性和无效参数不输出半张表。
管理器清单改为 `hdr-curve` 分支的 `d44cb95`，干净源码可构建文档描述的 HDR 控件。

common_drivers `305ab27e9` 将 sysfs `reload_hdr` 改为提交待处理标记，由采集中断
在 isr_lock 下消费。VDIN0 的 HDR 寄存器实际直接写入，不是旧注释描述的 vsync
RDMA 排队；从 sysfs 直接调用会与信号切换中断共用 LUT 缓冲区。停止采集时请求
保留，恢复帧后处理；重复请求合并。主内核保持 `b86c7e5bd`。

独立目录按清单检出，locked 检查、42 项主仓库 Python 测试、30 项 NanoKVM
部署测试、10 项管理器助手测试、16 项 JetKVM 部署测试通过；完整用户态构建、
VIM4/默认 Go 目标测试与构建、前端和 sudoers 检查通过。六组件包
`2.5.1+vim4.20261014.1` 的隔离校验通过，包括音频启动顺序、ARM64 ELF、动态库、
配置保留、旧助手清理和损坏文件拒绝。内核 modules 构建通过。

板上其他应用包含独立任务改动，因此仅更新 vim4-kvm-board 包与 aml_media.ko，
不使用会覆盖全部组件的 deploy 入口。安装前模拟 APT，实际仅升级板级包；更新
initramfs、sync 后重启。旧模块、initramfs 和板级脚本备份在
`/var/lib/vim4-kvm/hdr-review-20261014.1/`。加载模块 build ID 为
`71e455238d105f4d2d9eff1da7a34b85db2efca9`，与产物一致。
NanoKVM、JetKVM、管理器二进制哈希均保持不变；管理器原有手工部署的 HDR 控件
继续工作。JetKVM 仍为 enabled/active，NanoKVM disabled。

重启后信源初始为 SDR，用户重新开启 HDR 后报告 HDR10-GAMMA_ST2084。
真实 Chrome 页面连续四轮预览 SDR 白 400→160→203、高光 1000：64×36 缩小画面
的平均 RGB 码值约 168.5→236.0→227.9，确认曲线确实影响解码像素，不是只更新配置。
这是桌面抽样，不是色度校准或 HDR 视频高光质量结论。预览不改保存值，保存恢复
203/1000；运行中增益和 sRGB 两张 LUT 与工具生成值逐项一致。

HDR 测试窗口约 12.56 秒，4K 解码 714 帧，浏览器 dropped/lost 均为 0；采集端
frames_dropped=0。HDMI InvocationID 在预览与保存前后保持不变。SDR 冒烟同样
零丢帧/丢包。board.py check 通过，无 failed units，dpkg audit 无输出，本次启动
日志未见 Oops/BUG/panic。未测 HLG、HDR10+、RGB/4:4:4、长期稳定性或端到端延迟。
日志、构建记录和界面截图在 `logs/hdr-review/`；产物及部署脚本在 `build/hdr-review/`。

## JetKVM 默认 EDID 改为 4K60 并部署（2026-10-14）

JetKVM `165f0aa` 将 VIM4 首次启动、空配置回退和界面“恢复默认”统一到已有的
VIM4 3840×2160 60 Hz 厂商表。已保存的预设和自定义 EDID 保留，原生 JetKVM
预设仍可手动选择。清单由主仓库 `4b98ca1` 固定该提交。独立源码验证通过
VIM4 全部 Go 测试、两种目标 go vet、前端与 ARM64 构建。

板上已有“重新连接显示器”功能，其对应未提交补丁在独立构建目录中保留，
没有纳入本次 Git 提交；助手与板上版本 SHA256 一致。部署包
`2.5.1+vim4.20261014.2` 的 sources.json 明确记录 kvm dirty=true，补丁归档为
`build/jetkvm-edid-deploy/preserved-kvm.patch`。完整组件构建及隔离包校验通过，
实际仅安装 vim4-jetkvm，短暂停止并重启该服务，没有重启板子或其他应用。
旧二进制、助手及配置备份在 `/var/lib/vim4-kvm/jetkvm-edid-20261014.2/`。

部署前保存的 EDID 已是 VIM4 4K60，配置文件在安装和服务重启前后哈希一致。
真实 Chrome WebRTC RPC 返回新应用版本，getEDIDPresets 第一项与 getEDID
均逐字节匹配该 4K60 厂商表。4K H.265 在 10 秒内解码 600 帧，dropped=0、
packetsLost=0；G.722 收到 500 包，但音频能量接近零，不能据此确认可听声音。
board.py check 通过，dpkg audit 无输出，无 failed units；NanoKVM、管理器和
HDR 曲线工具哈希未变。未另测恢复出厂设置、冷启动及运动画面质量。
本轮记录在 `logs/jetkvm-edid-deploy/`，构建产物在 `build/jetkvm-edid-deploy/`。

## 2026-10-14：One-KVM VIM4 与三套界面切换

已建立 `vim4-kvm/One-KVM` fork。One-KVM `vim4` 分支 `0c753be4` 使用独立
Cargo feature 接入 vfm_cap、amlvenc、板级 HID 和单 LUN 虚拟介质；保留上游认证
与界面。管理器 `onekvm` 分支 `7489ba1` 同时包含三套应用选择、HDR 调节和
原有 CPU、内存、温度、风扇图表，主仓库 `0841e3f` 固定对应源码。

首次部署管理器时漏带另一工作树的图表，用户指出后已合并、测试并重新部署。
最终浏览器检查确认 4 项趋势、5 个图表 SVG、HDR 面板和 One-KVM 入口同时存在。
图表历史为管理服务内存数据，重启后重新采样。

完整隔离构建生成 `.20261014.3` 七组件包，Go、Python、前端、Rust 构建与包校验
通过。实机发现首次通用配置归一化会关闭 MSD，VIM4 默认配置现显式恢复启用，
并保留已经初始化用户的选择；修复后 554 项 Rust 测试通过。
最终包 `2.5.1+vim4.20261014.4` 重建 One-KVM 和管理器，复用同源码版本的其余
五项已验证产物，sources.json 记录该增量关系，全部源码 clean。七包的 SHA256、
ARM64 ELF、动态库、sudoers、配置保留和损坏文件拒绝检查通过。

实机只安装 One-KVM 和管理器 `.20261014.4`；NanoKVM 保持 `.20261013.10`，
JetKVM 保持 `.20261014.2`，保留其现有功能与配置。按用户要求初始化独立网页账户，
未改系统及其他应用账户。管理器当前选择 One-KVM，其他两套应用停止且不开机启动。

实测输入为 3840×2160、59.98 Hz、YUV420、SDR。真实 Chrome H.264 10 秒解码
约 600 帧，H.265 约 598 帧，均未观察到丢帧和丢包。六次带旧会话的三应用切换均
恢复 4K、约 60 fps，首帧约 2.2–4.1 秒；HDMI 服务 InvocationID 全程未变。
最终包再次验证 H.264 约 59.96 fps；MJPEG 连续收到三帧 3840×2160 JPEG，随后
恢复原 H.264 模式。以上为当前桌面场景，不代表运动质量或端到端延迟测试。

音频 Opus WebSocket 经浏览器解码得到 5 秒、240000 帧非零 PCM，峰值约 0.832。
WebRTC 音轨收到数据，但其统计能量为零，不能把此项当作可听 WebRTC 音频证据。
键鼠经 One-KVM 认证 WebSocket 驱动，Mac 实际光标位置及 Shift 状态验证通过。
上传只读 ISO 后，Mac 读出测试文件；挂载和弹出后键鼠仍正常。测试镜像已清理，
USB 恢复 NCM 和三项 HID，未出现新内核 panic/Oops。未做冷启动、外网穿透或
HDMI 热插拔验证；无 ATX 硬件，多 LUN、USB 麦克风和上游通用固件更新不开放。

`board.py check` 通过，`dpkg --audit` 无输出。最终包在
`build/packages/2.5.1+vim4.20261014.4/`，测试日志及管理器截图在 `logs/one-kvm/`。

## 2026-10-14 One-KVM 输入状态与流设置

One-KVM `c4364572`，打包入口 `eac6414`，正式组件版本
`2.5.1+vim4.20261014.5`。仅升级板上的 vim4-onekvm；manager 保留 `.4`，
NanoKVM、JetKVM 及其已有部署改动未覆盖。包使用固定 ARM64 Ubuntu builder，
One-KVM 重新编译，其余六项复用 `.4` 中源码版本不变的产物；sources.json 记录此关系。

输入状态接口原先把 `/dev/video_cap` 当作普通 V4L2 节点拒绝，改为直接读取 HDMI RX
sysfs，观看期间可返回 3840×2160、59.98/59.99 Hz、NV21。NV21 表示采集输出格式。
输出设置与源信号独立，支持原尺寸/720p/1080p/2160p 上限、帧率上限、MJPEG 质量、
H.264/H.265 码率、EDID 预设和共享 HDR 曲线。

首次 GE2D 连续切编码测试暴露厂商 DMA 分配器重复关闭 fd，进程报
`safe_close ... EBADF`。私有分配器将 fd 仅交给 GstDmaBufMemory 管理，
随应用部署且不替换系统库；另提供 gfx2d 所需的同步入口，使用独立 GStreamer 注册缓存。
修复后完整切换过程中 `NRestarts=0`。

验证：

- 前端构建、557 项 Rust 单元测试、4 项特权助手测试、42 项工作区测试通过；
  私有分配器的 100 次缓冲区引用/释放生命周期测试通过。
- 七组件包的校验和、ARM64 ELF、动态依赖、sudoers、配置保留与损坏文件拒绝检查通过。
  APT 预检只升级 One-KVM，安装后 `dpkg --audit` 无输出。
- Chrome 实际解码：H.264 1920×1080 29.97 fps，H.265 1280×720 14.98 fps，
  恢复 H.264 3840×2160 59.97 fps。观看过程中改 1080p→720p→1080p 无需刷新页面。
- MJPEG 1080p 质量 35 的每帧约 141 KB，质量 90 约 347 KB；页面质量表单也实际提交成功。
  保持 MJPEG 观看时改 EDID，输入先变为 1920×1080，再恢复 3840×2160，两次均继续收到 JPEG 帧。
- 重启 One-KVM 后输出限制与质量保留；EDID 1080p/4K60 可往返，HDR 220/1200
  可保存并恢复 203/1000。当前输入为 SDR，本次没有验证 HDR 曲线对 HDR 画面亮度的影响。
- 全程 HDMI 服务 InvocationID 保持 `5adb6d1c9b494584996befd0f64d2877`。
  管理页面 5 个 SVG 图表仍存在，`board.py check` 通过。

收尾恢复为 H.264、跟随输入尺寸/帧率、Balanced 码率、MJPEG 质量 80、4K60 EDID、
HDR 203/1000。日志位于 `logs/one-kvm-settings/`；`source-recovery.log` 的视频验证通过，
末尾图表检查误用 canvas 选择器，已在独立的 `manager-charts.log` 按实际 SVG 实现复核通过。

## 2026-10-14 One-KVM 虚拟盘初始化修复

创建 256 MiB 虚拟盘失败的原因是 Ubuntu 包未包含 Ventoy 引导资源；服务启动时
报告 `boot.img not found`，创建时报 `Resources not initialized`。普通 ISO 挂载
不会覆盖此路径，之前的虚拟盘单元测试又因错误的资源目录直接跳过，未能发现缺项。

One-KVM `5b3df497` 从 `/usr/share/vim4-onekvm/ventoy` 加载 VIM4 包内资源；
主仓库 `a2f6b76` 将仓库自带 boot.img、core.img.xz、ventoy.disk.img.xz 解压打包，
安装及验证检查拒绝缺失资源。用户盘位于独立的数据目录，升级不覆盖。
修复测试资源路径，在临时目录解压，缺失或损坏时测试失败，不再静默跳过。

仅升级 `vim4-onekvm` 到 `2.5.1+vim4.20261014.6`。557 项 Rust 测试（包括实际
创建、目录、文件读写和流式读取）、42 项工作区测试、4 项助手测试及 release 构建通过；
七组件包校验通过。`dpkg --audit`、`dpkg --verify vim4-onekvm` 均无输出。

服务 05:35:04 UTC 成功加载资源，用户随后于 05:35:22 创建 268435456 字节虚拟盘，
05:35:25 挂载到 LUN 0。macOS 识别 USB ExFAT 卷 `/Volumes/ONE-KVM`，只读验证
完整读取盘内 8343098 字节文件。保留用户正在使用的虚拟盘及连接，没有重建或卸载。
HDMI InvocationID 仍为 `5adb6d1c9b494584996befd0f64d2877`，One-KVM 和管理器均 active。

新增端到端脚本 `tools/one-kvm-drive-check.mjs`；首次执行因读取状态响应层级错误
在修改介质前退出，已修正为 `status.state` 并通过语法检查。因用户已开始使用虚拟盘，
没有完整重跑自动上传/下载/卸载流程，也未验证 Ventoy 启动操作系统。
日志位于 `logs/one-kvm/ventoy-*.log`。

## 2026-10-14 One-KVM 本地扩展、看门狗与包更新

One-KVM `0989e476`，最终安装 `vim4-onekvm 2.5.1+vim4.20261014.8`。
主仓库 `709f0f0` 是包的源码记录；更新验证脚本随后在 `7e427a8` 修正重启后的重新登录。
保留其他 KVM 和管理器原版本，仅新增终端所需的 libwebsockets 运行库。
中间 `.7` 包引入 Ubuntu ttyd 守护包；发现其默认启动独立服务后，`.8` 改为
包内私有终端程序，移除本轮安装的 ttyd 包。不会额外启动独立终端服务。

新增运行目录和终端就绪等待，解决 spawn 后立即连接 Unix socket 的竞态。
Gostc 2.0.9、EasyTier 2.4.5、FRP 0.71.0 的 ARM64 制品与许可证随包安装，
下载 SHA256 固定在 `packaging/ubuntu/extensions.lock.json`。仅 EasyTier 程序具有
cap_net_admin。硬件看门狗通过服务的专用附加组访问，不放宽为全局可写。

网页更新使用 VIM4 专属平台标识和包版本；下载大小/SHA256、deb 包名/架构/版本、
APT 依赖计划、安装文件校验和重启流程均已接通。构建生成两个更新清单；
公网 Release 尚未发布，不能将本地流程通过写成公网通道已上线。

验证：

- 前端构建、VIM4 release 构建、558 项 Rust 测试、7 项助手测试、42 项工作区测试通过。
- 七组件包校验通过；隔离容器实际验证 deb 升级、保留数据、拒绝重复版本和降级。
  同一容器还运行生产程序，验证认证 API → 清单 → 下载校验 → 安装 → exec 重启 → 重新登录。
- 最终包网页终端实际执行 `id -un` 返回 khadas；Gostc 可启停；EasyTier 创建 TUN
  并在停止后清理；FRP 经仅监听 loopback 的临时 frps 转发 One-KVM HTTP 成功。
- 看门狗开启、初始喂狗及运行检查、安全关闭通过；结束时 sysfs state 为 inactive。
  未进行强杀应用或等待超时导致整机复位的破坏性测试。
- 最终包 WebRTC 视频 3840×2160、59.97 fps，采样中无丢帧/丢包；输入 HDMI 测试音后，
  Web Audio 从真实 WebRTC 轨道采样峰值 0.620，证实解码得到非零音频。
  totalAudioEnergy 仍为 0；单靠此统计判定静音会误判。

用户选择先完成本地适配，公网服务器稍后配置。测试结束恢复各扩展原配置并关闭，
检查脚本显式还原 GET 隐去的空密钥和空完整配置，并比对还原结果；临时 frps、
测试配置及 TUN 均清理。安全弹出后恢复原 256 MiB 虚拟盘，未重建盘或删除用户文件。
One-KVM 和管理器 active，`dpkg --verify vim4-onekvm`、`dpkg --audit` 无输出。
HDMI InvocationID 始终为 `5adb6d1c9b494584996befd0f64d2877`。

普通 ARM 默认目标的额外编译检查被 Ubuntu FFmpeg 缺少 AV_HWDEVICE_TYPE_RKMPP
阻塞；VIM4 feature 构建与测试通过，未将该通用目标检查报告为通过。
日志位于 `logs/one-kvm/features-*.log`。其余未接硬件和未验收功能见
[功能复核](one-kvm-audit.md)。

## 2026-10-14 One-KVM HID 功能配置与 USB 组合

最终 One-KVM 源码 `98ba6784`，主仓库打包基线 `f71b586`，安装
`vim4-onekvm 2.5.1+vim4.20261014.10`。仅更新 One-KVM；管理器保持 `.4`，
JetKVM `.2`、NanoKVM `20261013.10`。包 SHA256：
`1be7a813d56373cd9e41c12cf1b873ca673b6c03097844b7a965fb95e1104a50`。

- HID 配置接入板级 gadget 的原有实例与链接；增加 hidg3 多媒体键及专用 udev
  权限。重枚举前释放按键并关闭设备，助手等待 udev 权限生效。描述符、磁盘名称、
  UAC2、NCM/ECM/RNDIS 可配置，网络使用独立 NetworkManager DHCP/NAT 连接。
- 端点预算为 5 个 IN，保存预留启用虚拟盘的一个端点，挂载时再校验。超限请求
  未破坏现有配置。禁用全部 HID 后重新启用通过；修复重复解除已解绑 UDC 返回
  ENODEV 的恢复问题。绝对鼠标单独启用时按钮/滚轮不再被丢弃。
- API 与网页保存通过，设备名写入实际 configfs。主机键盘 Shift、鼠标定位、
  只读 ISO 内容读取、弹出后键鼠恢复通过。切换虚拟盘开关时也使用包内 Ventoy
  资源目录，避免重新初始化时错误回到数据目录。
- UAC2 在板上 ALSA 和 macOS 枚举，认证 WebSocket PCM 触发实际 ALSA 消费进度。
  macOS 设备显示 `Capture Inactive`，厂商 One-KVM。录音终端权限状态为未授权；
  零波形不算音频验收通过，完整主机录音仍待授权。未修改系统默认输入。
- NCM/ECM/RNDIS 均分配板侧 `10.42.0.1/24`，停止服务后删除本应用网络连接，
  恢复原始 VID/PID、名称及 HID×3+NCM。Windows 驱动与完整 NAT 数据流未验收。
- One-KVM → NanoKVM → JetKVM → One-KVM → JetKVM → NanoKVM，再恢复 One-KVM，
  每轮 3840×2160、约 59.66–60.05 fps，所测区间未观察到丢帧或丢包。
  HDMI InvocationID 始终 `5adb6d1c9b494584996befd0f64d2877`。
  NanoKVM 的既有预设在切换时自动挂载了其 512 MiB 虚拟盘，结束后在主机安全弹出、
  从 gadget 卸载，恢复测试前的未挂载状态；没有删除镜像或改其持久配置。
- Rust 560 项、Python 助手 15 项、工作区 42 项通过；前端与 ARM64 release 构建、
  包校验、隔离容器完整在线升级测试通过；板上 dpkg 校验与 audit 无错误。

证据：`logs/one-kvm/usb-api-final.log`、`usb-input-media-final.log`、
`usb-switch-final.log`、`usb-package-final-verify.log`、`usb-settings.png`。
暂不支持多 LUN、任意磁盘目录和以太网桥接，界面给出组合限制及说明。

## 2026-10-14：4K60 高码率编码实验

使用临时插件将实验参数范围提高到 100 Mbps，H.264/H.265 各测
20/30/40/60/80/100 Mbps，所有档位约 60fps，12 份完整码流独立解码通过。
H.264 100 Mbps 设置下实际平均 61.34 Mbps、1 秒峰值 72.02 Mbps；
H.265 同一运动画面约 26 Mbps 趋于平缓。未测出绝对硬件上限，未完成
网络、浏览器、长期热稳定或画质验收。已恢复 One-KVM，HDMI 未重启，
已安装插件及应用设置没有变化。方法、数据和限制见
[高码率实验](encoder-high-bitrate.md)。

## 2026-10-14：三套 KVM 自定义 60 Mbps 部署

已部署完整组件包 `2.5.1+vim4.20261014.11`。NanoKVM、JetKVM、One-KVM
及 amlvenc 由固定提交重新构建；未改动的板级工具、采集插件和管理器二进制
复用 `.10` 验证包，sources.json 记录来源。工作区未提交的 EDID 等改动未打包。
三套应用自定义范围均为 1000–60000 kbps，JetKVM 新增自定义输入，原档位保留。

- 干净源码构建及包校验通过，包括 ELF/依赖、配置保留、损坏文件拒绝和真实升级流程。
  JetKVM 的副本 Git 对象路径在容器内不可用，最终构建使用 `-buildvcs=false`；
  源码版本由包清单记录，应用版本显式写入 `.11`。
- 逐套切换并实际保存 60 Mbps，拒绝越界请求，刷新后读取配置；Chrome 解码
  3840×2160：One-KVM 59.67fps、NanoKVM 60.07fps、JetKVM 59.98fps，
  每次采样 10 秒，无观测到的丢帧/丢包。这是功能回归，不是持续带宽压力测试。
- NanoKVM 第一次检查因共用 URL 的缓存页面超时；测试入口加应用参数后通过。
- 恢复原码率及 One-KVM 选择；NanoKVM/JetKVM 配置文件 SHA256 与测试前一致。
  切换时 NanoKVM 自动挂载的磁盘已先在 Mac 弹出、再卸载，恢复测试前未挂载状态。
- 所有组件版本为 `.11`，dpkg 文件校验/audit 通过，管理器图表功能保留。
  HDMI InvocationID 仍为 `5adb6d1c9b494584996befd0f64d2877`。

证据：`logs/encoder-high-bitrate/package-verify.log`、`deploy.log`、
`apps-60m.log`、`nano-60m.log`、`jet-60m.log`；安装包位于
`build/packages/2.5.1+vim4.20261014.11`。实验硬件极限仍见前一节，
未新增高运动长时压力、端到端延迟或画质结论。

## 2026-10-14：One-KVM 高码率连接偶发退化到 10fps

在 `.11`、3840×2160 H.264、60 Mbps 设置下复现：服务端约 60.03fps，
Chrome 接收/解码仅 9.15fps；RTP 丢包及解码丢帧均为零，但关键帧达到
4.59 个/秒。首次 120 秒采样也出现 6–10fps。不是 HDMI 输入或帧率设置限制。

VIM4 连续采集不会等待订阅者，单槽发送队列在大关键帧发送期间溢出，丢失
参考帧后重新请求关键帧，形成反复恢复。One-KVM `1bc36e3c` 为 VIM4 增加
最多 8 个编码批次的突发缓冲（VIM4 每批一帧），持续慢订阅者仍走既有丢帧
与关键帧恢复逻辑；其他平台保持单槽。新增确定性的关键帧发送期间参考帧连续
性测试，原单槽背压、慢订阅者隔离测试继续覆盖，561 项 Rust 测试通过。

已构建、校验并部署完整 `.12` 包，仅 One-KVM 二进制变化，其余组件复用
`.11` 验证产物。相同 60 Mbps 设置下连续 180 秒 Chrome 采样，去掉起始
两个采样后的 174.7 秒平均 59.99fps，服务端 60.00fps，关键帧 1.00 个/秒，
零冻结、零丢包、零解码丢帧。实际接收码率 35.28 Mbps；目标码率不是固定吞吐。
平均解码耗时从 12.12 降至 4.05ms，浏览器抖动缓冲平均等待从 57.99 降至
40.72ms；这些指标不代表端到端输入延迟，不能将缓冲帧数当延迟保证。
随后重新连接和页面刷新各采样约 30 秒，稳态平均 59.97/60.07fps，
零丢包、零解码丢帧；两段连接统计各有一次启动期冻结计数，未复现持续 10fps。

证据：`logs/one-kvm/fps-diagnosis/` 下 `chrome.jsonl`、
`baseline-server.jsonl`、`fixed-server.jsonl`、`reconnect.jsonl`、`tests.log`、`verify.log`、
`deploy.log`。未改变用户码率和输出配置，HDMI 服务未重启。


## 2026-10-14：Wave521 时钟与编码耗时

4K 每帧硬件编码 H.264 11.55ms、H.265 12.96ms（666 MHz），与码率无关，
随时钟反比变化。借用 gp1_pll 超频到 750/800 MHz 后，同一输入的码流
不再逐字节一致；600 MHz 对照一致。结论为不超频，维持 666 MHz。
详见 [编码实验记录](encoder-experiments.md#wave521-时钟与-4k-编码耗时2026-10-14)。

## 2026-10-14：4K60 编码链路抖动与丢帧检查

NanoKVM 现有配置（3840×2160、30000 Kbps、GOP120、cbr），Mac HDMI 运行
`latency-source --motion`，Chrome 单 viewer 采样 60 秒，临时开启
VIM4_VIDEO_TIMING 与 vfmcapsrc 计时，结束后已移除并重启服务。

- 板端稳态 3736 帧、59.998fps：采集序号无间断，采集间隔 p99 16.81ms、
  最大 24.05ms；DQBUF 等待 p99 0.06ms；vfm_cap frames_dropped 为 0。
- 采集到应用拷贝：P 帧 p50 11.98 / p99 14.91ms；关键帧 p50 18.45ms，
  超过 16.7ms 但未造成后续积压或丢帧；最大一次 37.70ms（关键帧），后续帧恢复。
- 编码输出间隔标准差 1.55ms；关键帧约 650KB，实际码率 30.88 Mbps。
- Chrome：60.0fps，丢帧、丢包、freeze、NACK、PLI 均为 0；抖动缓冲平均 2.25ms，
  解码帧间隔标准差 7.64ms，大于板端编码输出抖动。

证据：忽略入库的 `logs/encoder-jitter/`（journal.log、chrome.jsonl、分析脚本）。

## 2026-10-14：WebRTC 视频分段卸载发送（.23）

板端抓 eth0 出口包定位到 4K 大 P 帧（约 300KB）发送需 9.0ms（p99 24.7ms），
约 280 Mbps：pion 每包一次 sendto（约 12µs 内核 CPU）且 Chrome 协商到 AES-CM/HMAC。
NanoKVM 172ddab：应答时作 DTLS 服务端以选 AES-GCM；playout-delay 只加在首包；
每个视频连接的 UDP 套接字在写帧期间收集数据报，以 UDP_SEGMENT 成批发送。
首版包装了 mDNS 组播套接字，读循环空转占用约 3 核，已改为不包装组播套接字。

| 30 Mbps 运动 4K、Chrome | 改前 | 改后 |
|---|---|---|
| 大帧发送 p50 / p99 ms | 9.0 / 24.7 | 3.6 / 9.2 |
| 末包相对采集时钟 p99 ms | 25.2 | 10.3 |
| 浏览器帧间隔标准差 ms | 8.1 | 5.9 |

新路径下 12/6/3 Mbps 的帧间隔标准差为 3.6/2.4/1.8ms；剩余波动主要来自随帧
大小增长的编码耗时。GOP 600 在 30 Mbps 下无明显收益。均零丢包、零丢帧。

`.23` 只更换 NanoKVM：在干净临时工作区以 .22 的其余提交（One-KVM 套用哈希相同的
.22 未提交改动）打包，主检出中他人未提交的 EDID、kvm、管理器改动未打包。
package/verify、board.py deploy、board.py verify（HID、音频、4K 60.1fps）通过；
部署后空闲 CPU 0%。`tools/video-smoke.mjs` 的 h265/direct 模式在 .22 上同样失效
（选择 H.265 仍协商 H.264，Direct 超时），属于脚本与当前前端不匹配，未修。
证据：忽略入库的 `logs/encoder-jitter/`。

## 2026-10-14：NanoKVM Wi-Fi 扫描空列表

板上 Wi-Fi radio enabled、rfkill 未封锁，但 wlan0/wlan1 均无 UP 标志，
NetworkManager 仍报告 disconnected；`wifi-scan` 返回空数组，`iw dev wlan0 scan`
返回 Network is down。经有线 SSH 将 wlan0 置 UP 后扫描恢复，首次返回 17 个热点。
接口最初被关闭的原因未确定，未据此归因驱动。

NanoKVM 的 vim4-system 增加扫描前检查：radio 禁用时报错，不擅自开启；
radio 已开启而接口 DOWN 时恢复接口。命令 locale 改为 C.UTF-8，修复中文 SSID
被 nmcli 的 C locale 替换为问号。仅更新板上该助手，无需重启 NanoKVM；
更新后助手返回 13 个热点且保留中文名称。网络数量随扫描变化。
部署助手测试共 35 项，32 项通过、3 项跳过；未使用路由器密码测试实际关联。

## 2026-10-14：提交工作区积累改动并部署 .24

将各仓库未提交源码分别提交：NanoKVM `28eafd8`（切换回来时恢复 EDID）、
JetKVM `7040219`（重新连接 HDMI 与共享 EDID 标记）、One-KVM `a2c450a1`
（Tight JPEG 不再要求客户端显式报告质量编码）。管理器 main 的趋势图 `dd37838`
与 onekvm 的三应用选择、HDR 控件合并为 `be7f4f0`，同时保留 Wi-Fi 开关。
工作区清单更新到上述提交，manager 开发分支统一为 main。未推送远端。

从干净源码（主仓库 `1fbf80e`）构建 `2.5.1+vim4.20261014.24`，七包 package、
隔离 verify、board.py deploy 均通过，从 .23 升级并保持 NanoKVM 启用。
构建覆盖 VIM4/默认 NanoKVM Go 测试、JetKVM 内部包测试、One-KVM 561 项 Rust
测试与管理器测试；One-KVM 助手 15 项在 root Ubuntu ARM64 环境通过，其 Mac
宿主测试因临时目录非 root 所有而失败，未将宿主结果计为通过。

板上浏览器确认三应用、趋势图、HDR 和 Wi-Fi 开关均存在。经有线管理连接实测
Wi-Fi 关闭/开启，并恢复开启；随后 NanoKVM 扫描返回 16 个热点。
board.py verify 的 HID 通过，视频为 3840×2160、约 60fps、零丢帧/丢包。
PCM 被 NanoKVM 音频会话占用，独立录音跳过；修正脚本管道末端返回 0 时把 busy
误判为零帧失败的问题。audio-smoke 经真实音量控件收取 6 秒 288480 个采样、
零丢包和补偿采样，能量为 0（信源静音）；不代表已验证有声输出。
最后主机工具 43 项测试通过。未测实际 Wi-Fi 关联、HDMI 重连按钮和 VNC 客户端实机。

证据：`logs/wifi-release/`；部署日志 `logs/board-20261014-211909-d8d81b/`。

## 2026-10-14：PiKVM VIM4 构建、集成和上板验证

kvmd `638d12e0`、uStreamer `60fe8b1`、管理器 `ec46f9c`，主仓库配方
`e1b6967` 从干净源码构建 `2.5.1+vim4.20261014.34`。仅升级 vim4-pikvm 与
vim4-manager，其他板级和编码包保持 `.24`，内核 `5.15.137-vim4kvm`。
Janus 1.4.2 固定上游提交和 PiKVM JS 补丁，无额外 Janus fork。

ARM64 package、隔离 verify、board.py deploy 通过；验证包括真实 Janus WebSocket
会话及插件 attach/destroy、动态依赖、配置和认证文件升级保留。主机工具 44 项、
管理器助手 15 项、介质助手 3 项、管理器 Go 测试通过。kvmd 上游测试在 ARM64
私有 Python 3.14 中 743 项通过、3 个警告；测试使用上游配置和测试专用 PAM 依赖。
uStreamer 默认与 WITH_VIM4 编译均通过。实现提交尚未推送。

实机是 VIM4 HDMI 输入连接 macOS，浏览器为本机 Chrome，局域网访问 8080。
`.34` 完整测试初始 10 秒收到 585 帧，3840×2160；该次浏览器累计丢弃 19 帧，
WebRTC 报告 packetsLost=0。该数值是此测试窗口结果，不是持续运动性能或延迟保证。
独立彩色动态信源测试取得 8 个不同解码图像哈希；播放 440Hz WAV，浏览器收到的
HDMI 音频峰值 0.1546。JPEG 快照、3840×2160 MJPEG 与 WebRTC 来回切换通过。
鼠标实际位置和 Shift 修饰键状态通过；ISO 上传后 macOS 读到预期标记，主机 eject、
PiKVM 状态同步和镜像删除通过。切换到 30fps/8000kbps/质量70并刷新后继续出帧，
最后恢复原参数。挂载 ISO 时管理器拒绝切换，应用和介质仍保持原状。

修复三项实机问题：VFM 无 duration 的帧需显式 videorate 输出 caps；HDMI centi-Hz
读数 5998/5999 抖动不能每次都重建编码器；普通用户登录会话结束后的 IPC 清理会
使正在运行的 memsink 名称消失，服务整组改用私有 /dev/shm。虚拟介质 host eject
不触发厂商内核 configfs inotify，复用现有轮询核对 LUN file；unmount 不能代替 eject。

测试结束恢复 NanoKVM active/enabled，PiKVM disabled；原 512MiB disk.img 挂载恢复，
macOS 再次识别 NanoKVM 磁盘，USB 麦克风和网卡均为关闭，与测试前一致。
PiKVM 可在管理面板选择；先在 USB 主机安全弹出当前虚拟盘。ATX 未接硬件、H.265、
USB 麦克风、NBD 直连和树莓派固件更新不属于当前集成能力；未验证长时间稳定性、
WAN/NAT、端到端延迟、断电恢复或 PiKVM 可刷入整机镜像。

证据：`build/pikvm-package-34.log`、`build/pikvm-verify-34.log`、
`logs/pikvm/deploy-34/`、`logs/pikvm/final-smoke-34.log`、
`logs/pikvm/switch-guard-34.log`、`logs/pikvm/restored-state.txt`。

### PiKVM 切入检查补漏

用户从已恢复虚拟磁盘的 NanoKVM 切入 PiKVM，prepare 因 LUN 非空拒绝启动；
旧管理器只检查 PiKVM 自己挂载的介质，已经停止并禁用了 NanoKVM。
管理器 `de596ac` 在 select/restart PiKVM 前检查任何现有 LUN，提前给出安全弹出
提示，保留原应用和开机选择。16 项助手测试通过；板上带原磁盘切换被拒绝，
NanoKVM 仍 active/enabled。macOS 安全 eject 后可正常切入 PiKVM。
修复以干净源码构建为 `.35`，隔离 verify 与 board.py deploy 通过。浏览器复测
3840×2160 WebRTC 持续出帧、JPEG 快照通过，最后保留 PiKVM active/enabled。
证据：`logs/pikvm/deploy-35/`、`logs/pikvm/entry-fix-smoke-35.log`。

### PiKVM HEVC、卡顿定位与全新 Ubuntu 组装

正式包 `2.5.1+vim4.20261014.39` 使用 kvmd `009975fd`、uStreamer `04e2756`、
管理器 `de596ac`。ARM64 构建、隔离验证与 board.py 部署通过。HEVC 使用硬件编码、
RFC 7798 RTP 分片和 Janus SDP；H.264 仍为默认，服务配置可选择 H.265，保留 MJPEG。
RTP 测试覆盖两种编码的单包、MTU 边界和多包重组；默认非 VIM4 构建也通过。
kvmd 验证器 673 项通过。浏览器测试现在通过登录表单进入应用，而非绕过登录流程；
新建无缓存浏览器上下文可正常登录，未修改登录跳转逻辑。

`.39` 板上 Chrome 实际协商 `video/H265`，3840×2160 解码、8 个不同运动图像哈希、
HDMI 音频峰值 0.15936、键鼠、ISO 主机读取与 eject、MJPEG/WebRTC 切换、参数保存
和刷新均通过。开发板保留 PiKVM active/enabled 和 H.265，未恢复 NanoKVM 挂盘。
证据：`build/pikvm-package-39.log`、`build/pikvm-verify-39.log`、
`logs/pikvm/deploy-39/`、`logs/pikvm/hevc-full-39.log`。

卡顿不是单纯缓存问题。稳定 60Hz 输入的 300 次 sysfs 采样出现 5987–5999 centi-Hz，
原 10 centi-Hz 阈值导致误重建，离线等待进一步产生秒级空窗。改为超过 1Hz、连续
两次稳定变化才重建，仍保留 3 秒无帧看门狗；默认 GOP 改为 30，避免没有周期关键帧。
修正前 H.265 五分钟测试最大浏览器回调间隔 1.8 秒、8 次 freeze；修正后没有编码器
重建，但同样五分钟仍报告 6 次 freeze、合计 2.609 秒，不能宣称卡顿已全部解决。

进一步同步测量：145 秒板端共享内存收到 8596 帧，P99 间隔 22.69ms，唯一超过
100ms 的间隔是连接建立时的 1.437 秒；随后编码输出连续。同期无缓存浏览器 120 秒
观察窗仍有 4 次 freeze、17 个丢包、最大画面回调间隔 583ms。剩余停顿发生在共享
内存输出之后，尚未区分 Janus 传输、网络与客户端调度。宿主仍有其他 Chrome 与
系统后台负载；这些是局域网桌面场景观测，不能代替独立机器持续运动或 WAN 验证。
证据：`logs/pikvm/hdmi-rate-observation.json`、`hevc-soak-final-37.log`、
`hevc-soak-debounce.log`、`hevc-arrival.json`、`hevc-soak-arrival.log`（后四项同目录）。

全新系统使用锁定的官方 Khadas Ubuntu 24.04/Fenix 1.7.5 基础镜像，加入 `.24`
六个基础组件及 `.39` PiKVM/管理器，内核 `b86c7e5bd`、驱动 `305ab27e9`。
八个额外 Ubuntu 运行依赖固定版本和 SHA256，先验证离线依赖闭包，再本地安装；
不依赖开发板的手工状态。修复 PiKVM 冷启动对 PD 服务的 Requires/After 顺序，
验证私有 Python 扩展、四应用动态库、默认服务唯一性、内核与设备身份初始化。
`vim4-kvm-ubuntu-pikvm39` 组装和只读离线验证通过；目前未刷写、未完成首次启动验证。
当前板子的 `/etc`、khadas 家目录和四应用数据已备份到
`build/backups/pikvm-before-image/config-and-data.tar.gz` 并检查 gzip 与 SHA256；
这是配置与数据备份，不是完整 eMMC 快照。刷写仍需明确清空 eMMC 授权。

### PiKVM 卡顿：ICE 选路与实际收包接口

继续定位时使用临时逐帧日志，比对 uStreamer 发布和 Janus 读取的时间戳。
有效连接窗口没有漏读；按 SSRC 抓取板端 RTP，7998 帧全部发出、序号无缺口，
最大帧发送间隔约 67ms。临时日志代码已移除，没有进入正式包。

Mac 的有线 en0 只有 IPv4，Wi-Fi en1 同时有 IPv4/IPv6。网页使用有线 IPv4，
浏览器 selected candidate pair 也报告远端 `192.168.50.210`，但对应 SSRC 的实际
视频几乎全从 en1 的 IPv6 收到；en0 只有少量探测包。该轮五次超过 100ms 的
画面间隔分别对应 139–213ms 的网卡收包空窗，画面恢复落后收包恢复约 12–23ms。
因此仅看网页 URL、ICE 统计或板端平均帧率，会漏掉这条无线媒体路径。

先临时关闭 Janus IPv6 做对照：视频走 en0，120 秒解码 7197 帧，零丢帧、零丢包、
零 freeze，最大画面回调间隔 50.1ms。随后恢复 IPv6，改用 `ice_nomination = "regular"`：
视频仍走 en0，120 秒解码 7200 帧，零丢帧、零丢包、零 freeze，最大间隔 33.5ms。
最终保留双栈，不修改电脑的网络配置。该观察说明本机双网卡场景下 aggressive
nomination 的媒体路径选择导致了剩余停顿，不代表无线网络自身的抖动已被修复。

kvmd `464a3558` 增加 VIM4 Janus 配置，主仓库 `7f53d27` 打包该配置并让隔离验证
启动实际安装的 Janus 配置；`.40` 构建、隔离 verify、board.py deploy 通过，
验证日志确认 regular nomination 生效。浏览器 soak 同时记录慢帧时间和 ICE 路径。
修正不需要额外 Janus fork；原 `.39` 镜像不含本次选路修正，应使用更新候选包。

证据：`logs/pikvm/h264-publish.tsv`、`h264-consume.tsv`、`h264-wire-trace.json`、
`h264-client-wire.log`、`h264-mac-en0.pcap`、`h264-mac-en1.pcap`、
`freeze-correlation.json`、`h264-ipv4-soak.log`、`h264-regular-soak.log`（同目录）；
`build/pikvm-package-40.log`、`build/pikvm-verify-40.log`、`logs/pikvm/deploy-40/`。

`.40` 正式包最终长测（3840×2160、60fps、12000kbps、GOP30，Mac 同时开启有线与
Wi-Fi，使用无缓存 Chrome 上下文）：H.264/H.265 各观察 300 秒，各解码 17998 帧，
两者 framesDropped、packetsLost、freezeCount、totalFreezesDuration 增量均为 0。
最大画面回调间隔分别为 33.5ms/50ms，P99 均约 33.4ms；H.264 窗口期间宿主还在
组装和压缩镜像。两种编码的独立运动检查各取得 8 个不同图像哈希；长测窗口本身
是桌面场景，不是持续高运动或 WAN 性能保证。H.265 额外复测音频峰值 0.16226、
键鼠、ISO 主机读取/eject、4K MJPEG 切换、设置保存与刷新，全部通过。
`dpkg -V vim4-pikvm` 无差异，临时诊断程序已被正式包替换；最终保持 PiKVM
active/enabled、H.265 开启、虚拟介质未挂载。整机 check 通过。
证据：`logs/pikvm/h264-final-40.log`、`hevc-final-40.log`、
`stability-summary-40.json`、`hevc-final40-route.pcap`（同目录）、
`logs/pikvm/final-state-40/`。

同步导出包含修正的 `build/images/vim4-kvm-ubuntu-pikvm40/`，配方 `7f53d27`，
默认 PiKVM/H.264。只读离线验证、压缩包/原始镜像校验和 flash dry-run 通过；
尚未擦除 eMMC 或进行新镜像首次启动。用户要求优先解决画面卡顿，当前完成的是
现有系统正式包上板回归与新镜像准备，不能将其表述为已通过刷机验收。
