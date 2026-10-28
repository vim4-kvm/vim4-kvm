# 内核

[vim4-kvm/linux](https://github.com/vim4-kvm/linux) 基于 Khadas 官方 `khadas-vims-5.15.y`
（4e557e233），工作分支 `vim4-kvm-5.15`；配合官方 fork
[vim4-kvm/common_drivers](https://github.com/vim4-kvm/common_drivers) 的同名分支。
发布名 `5.15.137-vim4kvm`，与原厂 `5.15.137` 的模块目录并存。
主内核工作树保留在 VM，Mac 不检出内核文件；不要以第三方整套内核替代官方基线。
2026-10-28板上实读为 `5.15.137-vim4kvm-hdrdual6`；7.3源码、保留运行时与功能差距见
[本轮复核](bringup/2026-10-28-kernel73-parity-audit.md)。以下为历史M0部署记录：
FullKvm 为v7.3 M0 `47878a0c611d`，release `7.3.0-vim4kvm-uhd1+`、
build ID `f483ea42fee88be39ea67c43478638be67334d6e`，含simpledrm控制台和既有Wave5防护。
九类完整回归、音频ENOLINK基线对照、专用DTB限制、整包哈希与3a61b75b回退备份见
[M0正式部署](bringup/2026-10-23-display-m0-r4.md)。下方厂商5.15流程保留。
正式版持久运行时支持与部署脚本见 [离线准备](bringup/2026-10-22-deploy-7-3-final-prep.md)；
第二轮即时 EDID 检查触发的回退另见 [历史窗口](bringup/2026-10-22-edge-7-3-final-deploy.md)。
7.x 使用 `/boot/edge` 与完整匹配模块，不使用下方的厂商 `kernel-install.sh`。

## 构建（OrbStack VM `vim4-build`，Ubuntu 24.04 arm64）

固定配置与 deb 打包入口为 `python3 tools/ubuntu-image.py kernel`，详见
[Ubuntu 镜像流程](ubuntu-image.md)。下方保留手工构建和板上回退说明。

macOS 文件系统大小写不敏感，内核树不能放在 Mac 上，只放在 VM 的 `~/src/linux`。`~/src/linux/common_drivers` 是 Mac 侧仓库的克隆，Mac 上改完推送后在 VM 里 `git pull`。

`.config` 取自板子 `/boot/config-5.15.137`，只改了 `CONFIG_LOCALVERSION="-vim4kvm"`。

```sh
cd ~/src/linux && touch .scmversion
M="make ARCH=arm64 CC=gcc-12 KBUILD_BUILD_VERSION=1 KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build"
$M olddefconfig && $M -j10 Image dtbs modules                 # 约 7 分钟
$M M=$PWD/common_drivers/drivers/media/vfm_cap modules        # vfm_cap 树外编译
```

打包：`modules_install INSTALL_MOD_STRIP=1 INSTALL_MOD_PATH=~/stage`，`vfm_cap.ko` 放 `lib/modules/R/extra/amlogic/` 后 `depmod`；`boot/` 下放 `vmlinuz-R`、`System.map-R`、`config-R`、`dtb-R/amlogic/kvim4{,n}.dtb`；打成 `vim4kvm-R.tgz`。

只改了单个模块（如 `vfm_cap.ko`、`amvenc_multi.ko`）时同理替换对应 `.ko`；vfm_cap 被 tvpath 引用时先 `echo rm tvpath > /sys/class/vfm/map` 再卸载。只改了 vdin 等 `aml_media` 内的驱动时，可只 `$M modules`，把 `common_drivers/drivers/media/aml_media.ko`（`strip --strip-debug`）覆盖到板上 `modinfo -n aml_media` 的位置，`depmod` + `update-initramfs -u -k R` 后重启。

## 安装

### HID 重新绑定

主内核 `dbcef7c1f` 将 f_hid 的等待队列、锁和接收链表初始化移到功能实例分配时；
`b86c7e5bd` 为每次绑定独立分配字符设备，旧设备由仍打开的文件持有到最后关闭。
两项缺一不可：只修等待队列的实机测试仍触发 list_del corruption。
旧实现每次 UDC bind 都重置等待队列，破坏仍注册在 epoll 中的 HID 文件描述符。
修复编进 Image（CONFIG_USB_F_HID=y），必须安装完整内核并重启，不能靠更换模块生效。
应用在切换 USB 功能前关闭 HID 的保护继续保留。

确认已经启动修复后的内核、停止 NanoKVM 并独占板子后，运行：

```sh
sudo python3 tools/hid-rebind-check.py --exclusive --fixed-kernel --cycles 20
```

此测试保持三个 HID 描述符注册在 epoll 中跨越 UDC 重新绑定，然后分别执行
显式注销和关闭。禁止在旧内核运行，它能触发已知 panic。测试后启动 NanoKVM，
再验证实际键鼠、音视频和内核日志。

### CRG USB 控制端点重连

CRG UDC 在总线重置时先进入 `USB_STATE_RECONNECTING`，等事件环排空后才由
`prepare_for_setup()` 清理 EP0 请求并重新启用 SETUP。此期间必须继续消费旧传输
完成事件，但不能处理新 SETUP；否则 SET_ADDRESS 会将仍在队列中的 `status_req`
再次入队，触发 `list_add double add` 和内核 panic。这与上面的 f_hid 生命周期问题不同。
仅恢复状态检查不足以解决解绑竞态：驱动还必须登记 `gadget.irq`，让 USB 核心在
解绑前等待已进入的中断完成，并在锁内检查异步回调开关。禁用期间不创建 SETUP/
STALL 请求、不调用 gadget 的 disconnect；请求完成事件仍可消费。旧代码释放锁后
检查开关并补发 STALL，可能跨过控制器重置而留下新的 EP0 请求。

`common_drivers/drivers/usb/crg/test_setup_events.py` 编译实际事件分派函数，验证
重连期间跳过新请求、旧完成事件仍可处理、恢复 DEFAULT 后可重新枚举。
运行 `python3 common_drivers/drivers/usb/crg/test_setup_events.py` 无需板子。
修改编入 `amlogic-usb.ko`；替换模块、更新 initramfs 并重启后，核对运行模块的
build ID，再做独占 USB 重绑定及各应用切换回归。不能只凭磁盘文件判断修复已生效。

### 自动风扇与编码器频率

主内核提交 `8df3bdb55` 增加 MCU 百分比调速；`cd7f74066` 修正紧急全速、
温度读取失败时全速、手动模式下改温度阈值不干预输出，以及同步取消调速任务。
两项提交已推送到 linux 仓库的 `vim4-kvm-5.15` 分支。对应模块为 `khadas-mcu.ko`：

```sh
make ARCH=arm64 CC=gcc-12 M=drivers/misc khadas-mcu.ko -j10
```

用此模块替换板上 `modinfo -n khadas_mcu` 的文件，执行 `depmod -a`、
`update-initramfs -u -k 5.15.137-vim4kvm` 后重启。测试策略函数：
`sh tools/test-fan-policy.sh /path/to/linux/drivers/misc/khadas-mcu.c`。

默认自动模式保留 60/80/100°C 阈值，连续曲线为 45°C→5%、55°C→25%、
60°C→35%、80°C→70%、100°C→100%；低于 45°C 停转。
每 30 秒采样一次，非紧急调速每次最多变化 5 个百分点；达到全速条件时立即
跳至 100%。`/sys/class/fan/speed` 是控制百分比，没有转速计反馈，不是实测 RPM。
三个阈值可在 vim4-manager 散热页调节，保存后由管理器开机恢复，不改设备树。

7.x 的 `drivers/thermal/khadas_mcu_fan.c` 已为 VIM4 增加同一默认安静曲线，
取 CPU、GPU、NNA、VPU、HEVC 六个温区的最高温度。启动和读温失败默认请求 15%，
有效温区高温时采用更高曲线输出，100°C 仍全速；读温故障或 MCU 写入失败 1 秒后重试。
正常 30 秒采样、5 个百分点调速，首次有效采样与故障恢复直接采用目标。
15% 为控制值，持续读温故障时散热余量低于原全速策略；变更与实板证据见
[启动风扇与恢复](bringup/2026-10-20-edge-recovery.md)。
此模式由一个内核任务独占控制，不同时注册给 `step_wise`，CPU 过热保护仍保留。
状态读 `/sys/bus/platform/devices/khadas-mcu-fan-ctrl/{speed_percent,temperature_millic,sensor_fault}`；
温度是上次采样值，百分比是最后成功写入值，没有测速反馈。
7.3已通过`trigger_temperatures`提供三档阈值读写，管理器helper及状态页已有7.x后端；
不能沿用早期“阈值调节未迁移”的结论，具体源码与版本见[差距复核](bringup/2026-10-28-kernel73-parity-audit.md)。

启动参数 `khadas_mcu_fan.quiet_auto=0` 恢复原 thermal cooling device：50°C 触发、
2°C 回差，`step_wise` 在 30–100 范围内调节。其他 MCU 型号保持此原实现。
离线检查用 `python3 drivers/thermal/test_khadas_mcu_fan.py`；驱动为内建，部署须更新
完整 Image 及同次构建的全部模块，不能仅替换 `.ko`。实测和回退见
[7.x 安静风扇](bringup/2026-10-20-edge-quiet-fan.md)。

`board/90-vim4-encoder.conf` 将 Wave521 A/B/C 三路设置为 666666666Hz。
原始 A 已为约 666MHz，B/C 为 500MHz。CPU、总线和电压保持默认。
`board/install.sh` 安装该配置；已加载的模块需重启系统后生效。
若模块被打进 initramfs，先运行 `update-initramfs -u -k 5.15.137-vim4kvm`。
回退：删除 `/etc/modprobe.d/90-vim4-encoder.conf`，更新 initramfs 后重启。
此配置是提频运行，短期测试通过不代表所有板子、负载和环境下均稳定。

### 完整内核包

```sh
scp vim4kvm-R.tgz tools/kernel-install.sh vim4:/tmp/
ssh vim4 'echo khadas | sudo -S -p "" sh /tmp/kernel-install.sh /tmp/vim4kvm-R.tgz'
```

脚本做的事：带 `--keep-directory-symlink` 解包（见 [内核与 /lib 事故](bringup/2026-10-12-custom-kernel-lib-symlink.md)）、复制 overlay 文件、备份 `extlinux.conf.stock`、写入 `Default`（新内核）+ `Stock`（原厂，显式路径）两个启动项、生成 initramfs、切换 `/boot/Image` 和 `/boot/dtb` 链接。

## 回退

U-Boot 出现 `Enter choice:` 菜单（5 秒）时经串口输入 `2` 选 `Stock`。永久回退：

```sh
sudo ln -sf vmlinuz-5.15.137 /boot/Image && sudo ln -sfn dtb-5.15.137 /boot/dtb && sudo ln -sf initrd.img-5.15.137 /boot/initrd.img
```

## 启动流程

U-Boot 读 p1 的 `/extlinux/extlinux.conf`；`APPEND` 中的变量来自 `/boot/uEnv.txt`；按空格可中断自动启动进 `kvim#`。overlay 从 `FDTDIR` 下的 `kvim4n.dtb.overlay.env` 读取（相对链接到 `/boot/overlays`），换 `FDTDIR` 后照常生效。

## 分支提交

| 提交 | 说明 |
|---|---|
| fix(usb): bound CRG UDC waits under HID load | HID gadget 压力下 UDC 等待有界 |
| fix(usb): quiet spurious xhci irq log | |
| vdin: Fix vdin1 stuck state after unclean V4L2 process death | |
| vdin: disable AFBCE/double-write | 960x540 降采样错误；vfm_cap 需要完整分辨率 MIF 输出 |
| arm64: dts: kvim4/kvim4n: tune fan auto thresholds | level0/1/2 = 60/80/100°C（驱动不读 level3） |
| media: add vfm_cap | VFM 链路 V4L2 抓帧 + DMA-buf 导出，支持无下游的 standalone 模式 |
| vdin: only force-stop on release by the V4L2 queue owner | 修正上面 vdin1 补丁：任何进程关闭 video70/71 都会强停 tvserver 启动的 vdin0 |
| vfm_cap: test_dmabuf: device path + frame dump | `tools/hdmi-capture.sh` 使用 |
| vfm_cap: count contiguous chroma plane in canvas size check | NV21/NV12 输出不再每帧被丢 |
| amvenc_multi: power off wave521 on last release | 原代码关电时调了 poweron，编码进程被 kill 后编码器卡死到重启 |
