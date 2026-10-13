# 内核

[vim4-kvm/linux](https://github.com/vim4-kvm/linux) 基于 Khadas 官方 `khadas-vims-5.15.y`
（4e557e233），工作分支 `vim4-kvm-5.15`；配合官方 fork
[vim4-kvm/common_drivers](https://github.com/vim4-kvm/common_drivers) 的同名分支。
发布名 `5.15.137-vim4kvm`，与原厂 `5.15.137` 的模块目录并存。
主内核工作树保留在 VM，Mac 不检出内核文件；不要以第三方整套内核替代官方基线。

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

脚本做的事：带 `--keep-directory-symlink` 解包（见 bringup-log §7）、复制 overlay 文件、备份 `extlinux.conf.stock`、写入 `Default`（新内核）+ `Stock`（原厂，显式路径）两个启动项、生成 initramfs、切换 `/boot/Image` 和 `/boot/dtb` 链接。

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
