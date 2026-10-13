# 内核与驱动

修改前读 [工作区](../workspace.md) 和 [内核构建、安装与回退](../kernel.md)。

MCU 风扇在 VM 主内核 drivers/misc/khadas-mcu.c，策略验证用 tools/test-fan-policy.sh。
VDIN、vfm_cap、Wave521、CRG USB 驱动在 common_drivers。
新 VIM4 使用 kvim4n.dtb；安装保留 stock 回退，不替换 /lib 符号链接。

单模块替换、initramfs 和完整包操作按内核文档执行。构建通过不代表启动、
温控、采集和 USB 已验证；硬件回归需要独占窗口。
