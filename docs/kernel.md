# 内核

khadas/linux `khadas-vims-5.15.y`（未修改）+ [vim4-kvm/common_drivers](https://github.com/vim4-kvm/common_drivers) `vim4-kvm-5.15` 分支。发布名 `5.15.137-vim4kvm`，与原厂 `5.15.137` 的模块目录并存。

## 构建（OrbStack VM `vim4-build`，Ubuntu 24.04 arm64）

macOS 文件系统大小写不敏感，内核树不能放在 Mac 上，只放在 VM 的 `~/src/linux`。`~/src/linux/common_drivers` 是 Mac 侧仓库的克隆，Mac 上改完推送后在 VM 里 `git pull`。

`.config` 取自板子 `/boot/config-5.15.137`，只改了 `CONFIG_LOCALVERSION="-vim4kvm"`。

```sh
cd ~/src/linux && touch .scmversion
M="make ARCH=arm64 CC=gcc-12 KBUILD_BUILD_VERSION=1 KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build"
$M olddefconfig && $M -j10 Image dtbs modules                 # 约 7 分钟
$M M=$PWD/common_drivers/drivers/media/vfm_cap modules        # vfm_cap 树外编译
```

打包：`modules_install INSTALL_MOD_STRIP=1 INSTALL_MOD_PATH=~/stage`，`vfm_cap.ko` 放 `lib/modules/R/extra/amlogic/` 后 `depmod`；`boot/` 下放 `vmlinuz-R`、`System.map-R`、`config-R`、`dtb-R/amlogic/kvim4{,n}.dtb`；打成 `vim4kvm-R.tgz`。

只改了 vdin 等 `aml_media` 内的驱动时，可只 `$M modules`，把 `common_drivers/drivers/media/aml_media.ko`（`strip --strip-debug`）覆盖到板上 `modinfo -n aml_media` 的位置，`depmod` + `update-initramfs -u -k R` 后重启。

## 安装

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
