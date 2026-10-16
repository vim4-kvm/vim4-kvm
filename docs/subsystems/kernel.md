# 内核与驱动

修改前读 [工作区](../workspace.md) 和 [内核构建、安装与回退](../kernel.md)。

MCU 风扇在 VM 主内核 drivers/misc/khadas-mcu.c，策略验证用 tools/test-fan-policy.sh。
VDIN、vfm_cap、Wave521、CRG USB 驱动在 common_drivers。
新 VIM4 使用 kvim4n.dtb；安装保留 stock 回退，不替换 /lib 符号链接。

单模块替换、initramfs 和完整包操作按内核文档执行。构建通过不代表启动、
温控、采集和 USB 已验证；硬件回归需要独占窗口。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| 向 Ubuntu 根目录直接解内核包，动态程序失效 | tar 替换 /lib 符号链接。安装必须带 --keep-directory-symlink，并保留 Stock 启动项 | [内核安装](../../docs/kernel.md)、tools/kernel-install.sh |
| USB 功能重新绑定后关闭 /dev/hidg*，内核 list_del panic | 5.15 f_hid 同时重置等待队列和仍被打开的 cdev。必须同时修复队列生命周期（dbcef7c1f）与独立 cdev 分配（b86c7e5bd）；只修前者实测仍会崩溃。保留应用保护，重启进入新 Image 才生效 | hid.Reenumerate、tools/hid-rebind-check.py、[内核](../../docs/kernel.md) |
| USB 重连期间 SET_ADDRESS 触发 list_add double add | 仅恢复 CRG UDC 的设备状态检查实测仍会 panic。还需登记 gadget.irq，让核心在解绑前同步中断；在锁内检查回调开关，禁用期间不补发 STALL 或处理新 SETUP。继续消费旧完成事件，不直接重置仍被硬件持有的请求链表 | common_drivers/drivers/usb/crg/test_setup_events.py、[CRG 重连](../../docs/kernel.md#crg-usb-控制端点重连) |
