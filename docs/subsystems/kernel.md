# 内核与驱动

实验性 Armbian edge 基线及构建见 [新内核基线](../kernel-edge.md)，不替代现有 5.15 发布流程。

构建、安装或回退内核时读 [内核构建、安装与回退](../kernel.md)；需要 VM 中的主内核工作树时读 [工作区](../workspace.md#构建)。

MCU 风扇在 VM 主内核 drivers/misc/khadas-mcu.c，策略验证用 tools/test-fan-policy.sh。
启动瞬间的风扇测试由 U-Boot board_init 向 MCU 0x96 写 1 触发，早于 Linux 温控；
禁用与验证见 [U-Boot 风扇记录](../bringup/2026-10-17-uboot-quiet-fan.md)。
VDIN、vfm_cap、Wave521、CRG USB 驱动在 common_drivers。
新 VIM4 使用 kvim4n.dtb；安装保留 stock 回退，不替换 /lib 符号链接。

单模块替换、initramfs 和完整包操作按内核文档执行。构建通过不代表启动、
温控、采集和 USB 已验证；硬件回归需要独占窗口。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 向 Ubuntu 根目录直接解内核包，动态程序失效 | tar 替换 /lib 符号链接。安装必须带 --keep-directory-symlink，并保留 Stock 启动项 | [内核安装](../kernel.md)、tools/kernel-install.sh |
| USB 功能重新绑定后关闭 /dev/hidg*，内核 list_del panic | 5.15 f_hid 同时重置等待队列和仍被打开的 cdev。必须同时修复队列生命周期（dbcef7c1f）与独立 cdev 分配（b86c7e5bd）；只修前者实测仍会崩溃。保留应用保护，重启进入新 Image 才生效 | hid.Reenumerate、tools/hid-rebind-check.py、[内核](../kernel.md) |
| USB 重连期间 SET_ADDRESS 触发 list_add double add | 仅恢复 CRG UDC 的设备状态检查实测仍会 panic。还需登记 gadget.irq，让核心在解绑前同步中断；在锁内检查回调开关，禁用期间不补发 STALL 或处理新 SETUP。继续消费旧完成事件，不直接重置仍被硬件持有的请求链表 | common_drivers/drivers/usb/crg/test_setup_events.py、[CRG 重连](../kernel.md#crg-usb-控制端点重连) |
| 在 FUSE 挂载上 inotify 后守护进程挂死、变僵尸 | 厂商内核为 inotify 发非标准 FUSE_CANONICAL_PATH(2016)；go-fuse v2.8 解析失败不回复，请求永久挂起。FUSE 守护进程必须对未知 opcode 回错误（go-fuse ≥ v2.12；空成功会越界）；卡死时写 /sys/fs/fuse/connections/N/abort 清理 | [NAS 存储与 U 盘](../bringup/2026-10-18-nas-storage-usb-disk.md) |
