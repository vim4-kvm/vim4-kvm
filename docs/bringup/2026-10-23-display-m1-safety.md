# 2026-10-23：M1 一次性启动与恢复安全网（仅离线）

第五窗口[RMFB 事故](2026-10-23-display-m1.md)说明：依靠候选 Linux 或 Mac 窗口
的 finally 写回基线不可靠。新机制保留默认启动文件，只在 U-Boot RAM 中选择一次候选。
本轮没有 SSH、串口操作、安装或重启；以下板级命令是下次窗口计划，不能当作实测证据。

## 现有固件支持与不变量

固定源码 `/home/deepdream/src/u-boot-pd-handoff`，提交 `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`。
`board/khadas/configs/kvim4.h` 提供 distro BOOTENV、`pxefile_addr_r=0x00010000`。
既有构建 `.config` 开启 `CONFIG_CMD_BOOTI`、`CONFIG_CMD_PXE`（同时注册 sysboot）、
`CONFIG_CMD_EXT4`、`CONFIG_FS_EXT4`；`CONFIG_CMD_EXT4_WRITE` 和 `BOOTCOUNT_LIMIT`
未开启，`ENV_IS_NOWHERE=y`。不假设 bootcount/saveenv 已可用，不改/刷 U-Boot。

`cmd/pxe.c:do_sysboot()` 接受 `sysboot <interface> <dev:part> any <address> <config>`，
从指定分区读取 extlinux 风格配置，Image/FDT 继续从同一文件系统加载。现有第五窗口
UART 确认 eMMC 为 U-Boot mmc1、默认启动分区为 1；Linux 根为
`PARTUUID=bcb80000-02`（p2 ext4，ordered）。根分区的 U-Boot ext4 兼容性仍需板上验证。

以下内容始终保留基线原件，不在候选暂存/启动流程里覆盖：

- `/boot/edge/Image`、`/boot/edge/vim4.dtb`、`/boot/extlinux/extlinux.conf`。
- `/etc/vim4-kvm/kernels.json`、`runtime-build.json` 和 `/lib/modules/7.3.0-vim4kvm-uhd1+`。
- U-Boot 持久环境、分区、引导区及正式 sources/workspace 锁。

所有候选文件放根分区 `/var/lib/vim4-kvm/display-m1/<build-ID>/`，避免 FAT 空间
不足而覆盖默认 Image。配置只有一个候选标签，沿用核对过的基线 APPEND，新增
`oops=panic panic=20 init=<私有路径>/init`。不注册到管理器，不在面板切换内核。

中断当次 autoboot 后只向串口发送：

```text
sysboot mmc 1:2 any ${pxefile_addr_r} /var/lib/vim4-kvm/display-m1/844bfec2f4240d42447e3dc35d2eee69cf2a0c8f/extlinux.conf; reset
```

不运行 saveenv，不改默认标签，不创建持久候选启动标志。读取/启动失败返回到 U-Boot
时执行 reset；候选运行后 panic 复位、看门狗复位或物理 RESET 均重新从原默认项启动。
无需候选 Linux“消费标志”或写回文件。**这不保证硬件硬锁时看门狗一定工作**；
`panic=20` 对不进入 panic 的整机挂死无效，仍可能需要用户 RESET。本轮未验证 watchdog。

## 同 release 模块隔离

现有 `vim4-board-runtime`、`vim4-kvm-run`、`one-kvm-edge-prepare` 对 release 精确匹配；
不能仅改候选 localversion 就声称 KVM 启动兼容。候选保留原 release，但完整模块另存
`<build-ID>/modules/<release>`，不在持久 `/lib/modules` 覆盖基线。

[display-once-init.c](../../packaging/kernel-edge/display-once-init.c) 编译为静态 ARM64 PID 1：

1. 挂载 proc/sys，核对 release、可执行路径末级 40 位 build ID 与真实 GNU kernel notes。
2. 核对源/目标目录为 root 所有、无 group/other 写权限，且不是同一目录。
3. 在 systemd/udev 前将私有完整模块目录 bind 到正常模块目录，再 remount bind 为只读。
4. 全部成功才 exec `/sbin/init`；任何预检或挂载失败立即请求复位，不启动候选用户态。

根文件系统及 MMC/ext4 驱动与基线一样内建、无 initrd；模块加载前完成 bind。
复位后初始挂载命名空间消失，基线没有 init override，正常使用原完整模块。
暂存不写数据库和应用文件，故新显示窗口退出无需还原应用数据库。

## 实现、离线命令与产物

[display-once.py](../../packaging/kernel-edge/display-once.py) 的 prepare 核对候选 Image/DTB/
模块归档哈希、逐模块清单、静态 ARM64 ELF，并保留大小写不同的模块名。
stage 是**需双锁的板级改动**：验证运行基线 build ID、release、cmdline 和五个受保护
文件哈希，只解包普通文件到 `.incomplete-*`，检查哈希并 fsync 后原子发布私有目录。
进程死亡留下的目录没有启动引用；stage 从不选择候选、不重启。
禁止归档链接、设备、绝对路径和 `..`；拒绝覆盖已有候选目录。

已在 VM 执行（无板子）：

```sh
gcc -static -std=gnu11 -Wall -Wextra -Werror -O2 \
  packaging/kernel-edge/display-once-init.c -o /home/deepdream/build/display-once-init
python3 packaging/kernel-edge/display-once.py prepare \
  --payload /home/deepdream/build/display-m1-payload-rmfb-6 \
  --init /home/deepdream/build/display-once-init \
  --baseline /Users/deepdream/Developer/github/localhost-copilot/vim4-kvm/logs/display/m1/window-5/baseline/state.json \
  --output /home/deepdream/build/display-m1-once-rmfb-6
```

prepare 在 Mac heavy 锁下运行，ARM64 ELF 无 INTERP/DYNAMIC；输出 `candidate.tar` 约 81MiB、
2351 个受哈希保护的文件，其中 2334 个内核模块，另含 trial.json。
首次归档 SHA256 `f8d75a41a05887dc957d0d9848ce0b2a21051a1cac20fff50779b4f8bc737ce7`。
实际候选 vmlinux `.notes` 导出后通过 PID 1 的真实 build gate。
本工具没有作为正式组件安装、没有变更基线文件。

离线测试入口：`python3 -m unittest discover -s tests -p 'test_display_once.py'`。
Mac 跑 Python 测试；Linux VM 额外编译执行真实 PID 1 syscall harness。
覆盖正常暂存、复制中断、子进程 `os._exit(91)` 无清理死亡、基线不变、错误 build ID、
动态/截断 ELF、危险 tar、大小写模块并存；PID 1 覆盖 release/build ID/归属/目录别名及
四次 mount 各自失败，均不能 exec systemd。真实挂载、固件加载、RESET 不属于这些 mock 的覆盖。

## 旧覆盖式 restore 的独立修复

[final-board.py](../../packaging/kernel-edge/final-board.py) 保留兼容旧窗口恢复入口，但 M1
不再使用它安装覆盖式候选。stop 每个服务最多等 10 秒；超时 kill 后不再次无界 wait，
非零退出同样记录并继续。优先恢复启动文件及模块，随后对本地文件系统 `sync -f`
（每次 30 秒上限），避免全局 sync 被无关 CIFS 挂载拖住。同步失败必须报错，不能宣称落盘成功。
daemon-reload 也有界且不阻止已经完成的启动文件恢复。

若任一服务没停成功，不覆盖可能仍被打开的 SQLite/WAL，留下 backup 中的
`application-restore-pending`；verify_restore 拒绝报告完整恢复。进入健康基线后协调新窗口，
重新运行该 backup 的 restore 才完成应用恢复与重新验证。旧事故不能以“启动文件已写回”
等同于“HID/应用已恢复”。文件系统自身 D 状态仍可能阻止写入；一次性启动把默认启动安全
从这条不可靠的候选恢复路径移走。

`tests/test_final_board.py` 故障注入覆盖任一/两个 stop 失败、超时后不二次 wait、
文件恢复→模块→sync 顺序、daemon-reload 失败不阻断、数据库延期和 sync 失败不报成功。

## 下次短窗口的顺序（尚未执行）

先协调其他 KVM 长验收任务；持 board/heavy 双锁执行一组即释放，不在等待时长期占锁。
不再运行旧私有 window.py。每个阶段有独立日志、备份名和失败停止条件。

1. 只读确认 `7b8372b8…` 及五文件哈希、服务含监控 active、UDC configured、isolated=0、
   taint=0、实际 HID；若基线已更新，停止并重新固定恢复目标/rebase/构建。
2. 在根分区私有 `baseline-check/` 放已校验的**基线副本** Image/DTB/config，不带 init
   override；串口 sysboot 该配置。确认根 ext4 可读、基线可启动，然后一次正常复位验证
   原默认项仍为基线。任一步失败即不进入 M1；不用刷 U-Boot“试一下”。
3. 才将候选 tar 传板，双锁下 `sudo python3 display-once.py stage candidate.tar`，
   复核受保护文件仍相同。串口当次 sysboot 候选；先短测图案关闭/RMFB、CRTC disable、
   连续 open/close，再 page flip 并抓物理画面。有 oops/taint/超时即停止，复位回基线。
4. 另约短组跑 4K60 H.264/H.265、输入音频连续性及 HID 共存，不把静态图当 KVM 通过。
   每次结束复位回基线，核对 build ID、服务含监控、UDC、isolated=0、taint=0、实际 HID。

当前只完成离线安全网；实际一次性启动及修复候选上板验证均待窗口。
