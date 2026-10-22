# 2026-10-21：7.3 IR 开机自动加载 Khadas 键表

将接收器改为模块后，完整重启进入候选内核，自动注册 rc-khadas 并启用 NEC；
没有手动 modprobe 或设置 ir-keytable。验证后恢复原 Image、DTB、完整模块目录，
再次重启确认原运行内核和文件校验通过。本轮执行 SSH reboot，未做断电再上电，
不能据此声称电气冷启动、物理遥控收码或唤醒通过。

## 改动与取舍

[首轮节点记录](2026-10-21-edge-ir-keys-spinor.md)中的 meson-ir 内建，
但 rc-khadas 和 NEC 解码器为模块；根文件系统就绪前查找键表失败，回落 rc-empty。
本轮只改主仓库 `packaging/kernel-edge/edge.config` 和 `uhd1.config` 中
`CONFIG_IR_MESON=y` 为 `m`，保留 `RC_CORE=y`、`RC_MAP=m`、
`IR_NEC_DECODER=m`、`IR_MESON_TX=y`。同步 UHD 配方是为了实际运行配置也包含修复。
未提交主仓库；`sources.toml` 中原部署产物的 tested_build 哈希未改，候选另列清单。

内核仍使用独立工作树 `/home/deepdream/src/linux-7.3-dtnodes`、分支
`vim4-ir-keys-spinor`、提交 `4c582adea35e936c84ac0a46172a1565905d926f`。
本轮没有新增内核源码提交，未改主工作树或并行 GPU 工作树。

依据该提交的 `drivers/media/rc/Kconfig`、`meson-ir.c`、`meson-ir-tx.c`、
`keymaps/Makefile` 及 rc-core：

- RX/TX 是独立 tristate，TX 不依赖 RX 的符号；没有发现要求 IR_MESON=y 的消费者。
  模块通过 OF alias 随平台设备自动加载，之后 rc-core 可以 request_module 查找键表。
- RC_MAP 统一控制所有内核键表；只内建 rc-khadas 需要拆分 Kconfig/Makefile。
  全部键表内建则扩大内核，且仍须考虑早期 NEC 解码器加载。采用接收器模块方案。
- 模块保留原 shutdown 和 suspend/resume 回调。shutdown 设置 NEC 硬解码模式，
  供 bootloader 尝试重新开机；suspend 原本会禁用接收器。没有据此推断 T7 实际唤醒能力。
  接收器在根文件系统/udev 就绪后可用，不提供早期启动阶段的 IR 输入；本板没有相关消费者。
- 本板 FullKvm 无 INITRD，CONFIG_INITRAMFS_SOURCE 为空，没有早期 initramfs 抢先加载问题。

## 配置与同次构建

两份配方分别执行 olddefconfig，最终均为 IR_MESON=m；IR_MESON_TX 保持 y。
UHD 最终配置相对首轮仅这一项变化，BTF、模块 BTF、XZ 压缩继续启用。

| 最终 .config | SHA-256 |
|---|---|
| 通用 edge，`~/build/kernel-ir-edge-config/.config` | `ea60195c2dcdad4211146db782ee2c6f5b38f450edecbd13c2a770879e23bc71` |
| 本次 UHD，`~/build/kernel-ir-autoload/.config` | `b67c0feeb849506467984d27fa75c9484d5dbe46073bb33b22bbfd6418d0c298` |

VM 使用 GCC 13.3.0，独立 O=，一次构建 Image、DTB 和全部模块：

```sh
cd /home/deepdream/src/linux-7.3-dtnodes
export SOURCE_DATE_EPOCH=$(git show -s --format=%ct HEAD)
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH")
make O=/home/deepdream/build/kernel-ir-autoload ARCH=arm64 olddefconfig
make O=/home/deepdream/build/kernel-ir-autoload ARCH=arm64 CC=gcc \
  KBUILD_BUILD_VERSION=1 KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build \
  -j8 Image dtbs modules
make O=/home/deepdream/build/kernel-ir-autoload ARCH=arm64 -j8 modules_install \
  INSTALL_MOD_STRIP=1 INSTALL_MOD_PATH=/home/deepdream/build/kernel-ir-autoload-stage
depmod -b /home/deepdream/build/kernel-ir-autoload-stage 7.3.0-rc7-vim4kvm-uhd1+
```

构建成功，编译日志未发现 warning/error。完整安装 2335 个 `.ko.xz`，比原基线多
meson-ir；modules.builtin 确认 TX 内建、RX 不再内建。DTB 仍取同次构建的 audio-test
变体，只用 fdtput 保留原以太网固定 MAC，包含首轮 IR/按键和禁用的 SPIFC 节点。

| 候选产物 | SHA-256 |
|---|---|
| Image | `038bde3aac5803da86bffcad40c406e44c8bdc063914fddfd29600bb76f12119` |
| vim4.dtb | `fd75a4fad4383974c46d7eb0c1b9684b74fd696f55278d72fb62aad7cff5cd09` |
| modules.tar.gz | `cbc97babc2316dc8cf065bb27f10ba3043d8cfbee2596983152a669bab8926f6` |

运行候选内核 GNU build ID 为 `81c0295959187206420f2c00616952aa5fbde64c`。
清单另记录完整模块文件哈希和 RX、键表、解码器、网口模块的 GNU build ID；
启动后逐一与磁盘及 sysfs 已加载实例核对，不以相同 release/vermagic 代替匹配证明。

## 上板命令与证据

Mac 全窗口持共享锁，覆盖备份、安装、两次重启及恢复检查：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-board.lock \
  python3 -u build/kernel-edge/ir-autoload/board-window.py
```

板上先备份至 `/var/backups/vim4-ir-autoload-20261021`，包含原 Image、DTB、extlinux、
完整模块 tar 及逐文件清单。候选模块先解到暂存目录，使用 `--keep-directory-symlink`，
再切换完整 release 目录，保留 `/lib -> usr/lib`。因 `/boot` 仅余 13MiB，旧 Image
备份到根文件系统后才移除并复制新 Image。5.15/Stock 启动项和链接保持原样。
没有停止 manager、手动加载模块、操作 Wi-Fi/P2P 或擦写 NOR。

候选 boot_id：`096b8d03-9a0e-4710-9a89-e2d92ef59c4c`。SSH 返回且 systemd 为 running 后，
首先读取 `/sys/class/rc/rc0/protocols` 和 `/proc/modules`，再执行无参数查询：

```sh
sudo /var/tmp/vim4-dtnodes-ir-keytable
```

```text
Automatic protocols before ir-keytable: rc-5 [nec] rc-6 jvc sony rc-5-sz sanyo sharp mce_kbd xmp imon rc-mm [lirc]
Automatically loaded: meson_ir 7fd89a7b6979120f216c888ff8fd11bc27e59487
Automatically loaded: rc_khadas 9a7acc440df9caefcbfb0616f29e6a3cf82d6948
Automatically loaded: ir_nec_decoder 0bc523f9234bf1aee4f5551a04a9d2f8f13915be
Automatically loaded: dwmac_meson8b c09dec1c9b58dec25c29ebc67b8fc84021086c05
Found /sys/class/rc/rc0/ with:
    Name: meson-ir
    Driver: meson-ir
    Default keymap: rc-khadas
    Input device: /dev/input/event2
    LIRC device: /dev/lirc0
    Enabled kernel protocols: lirc nec
```

对应 dmesg：

```text
[    4.653854] Registered IR keymap rc-khadas
[    4.725843] rc rc0: meson-ir as /devices/platform/soc/fe000000.bus/fe084040.ir-receiver/rc/rc0
[    4.798277] meson-ir fe084040.ir-receiver: receiver initialized
VERIFIED: automatic rc-khadas and NEC, complete module hashes and loaded build IDs
```

未执行任何 `ir-keytable -c/-w/-p` 或模块加载命令。本轮仅证明重新启动后的自动注册、
键表/协议选择及匹配模块实际加载；未物理按遥控器、未测试收码和挂起/关机唤醒。
没有可用且已确认的远程断电控制，未完成断电冷启动这一项。

## 恢复

脚本在 finally 中恢复原 Image、DTB 和完整原模块目录，再重启；新 boot_id 为
`1d00e79f-2fc9-4a26-bce9-ab1d01c36432`，systemd 为 running。恢复核对实际输出：

```text
/boot/edge/Image: OK
/boot/edge/vim4.dtb: OK
/boot/extlinux/extlinux.conf: OK
/boot/uEnv.txt: OK
/boot/vmlinuz-5.15.137: OK
/boot/initrd.img-5.15.137: OK
/boot/vmlinuz-5.15.137-vim4kvm: OK
/boot/initrd.img-5.15.137-vim4kvm: OK
All original module files and symlinks: OK
Original running kernel build ID: ['7aa593508a6e987e754de0e343498dbbc8c2edd7']
vim4-manager: active; original boot links and command line: OK
RESTORED after reboot
```

Image 恢复为 `25241ef8c402619e6917e6826129ba301c4b4dfacc4665db365620e9489faa48`，
DTB 恢复为 `471fc2881ed6c83726ac1db85277aaeadbb63eb6b608d821f2e0bc177d96a567`；
全部原模块文件、符号链接、启动参数匹配备份。原 DTB 没有 rc 节点，恢复后无 rc 设备。

主仓库检查 `python3 -m unittest discover -s tests -p 'test_*.py'`：
`Ran 147 tests`、`OK (skipped=5)`；`git diff --check` 通过。主仓库未提交，
并行 GPU 记录及其索引保留。

本轮临时脚本、产物、manifest 位于 Mac `build/kernel-edge/ir-autoload/`；
原始上板日志 `logs/kernel-edge/ir-autoload/board-window.log`，构建/配置/打包日志同目录。
VM 保留 `~/build/ir-autoload-{build,config,package}.log`、`ir-edge-config.log` 和独立 O=。
