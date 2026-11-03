# 内核与驱动

## 架构与约束

当前内核身份、主线配方与 Mainline/Vendor 布局统一见[主线内核开头](../kernel-mainline.md)。
Mainline 的 BCM43752 使用 .217 SDIO 固件和配套 brcmfmac/WCC 模块；
PHY trap 固件内部根因未确认，P2P 尚缺真实对端协商与传输验收。

MCU 风扇在 VM 主内核 drivers/misc/khadas-mcu.c，策略验证用 tools/test-fan-policy.sh。
7.x 对应 drivers/thermal/khadas_mcu_fan.c，VIM4 默认安静自动调速；验证用同目录
test_khadas_mcu_fan.py。控制值和回退见 [安静风扇](../bringup/2026-10-20-edge-quiet-fan.md)。
IR/按键注册及 NOR 与 eMMC 引脚限制见 [设备树节点记录](../bringup/2026-10-21-edge-ir-keys-spinor.md)。
启动瞬间的风扇测试由 U-Boot board_init 向 MCU 0x96 写 1 触发，早于 Linux 温控；
禁用与验证见 [U-Boot 风扇记录](../bringup/2026-10-17-uboot-quiet-fan.md)。
VDIN、vfm_cap、Wave521、CRG USB 驱动在 common_drivers。
新 VIM4 使用 kvim4n.dtb；安装保留 stock 回退，不替换 /lib 符号链接。

单模块替换、initramfs 和完整包操作按内核文档执行。构建通过不代表启动、
温控、采集和 USB 已验证；硬件回归需要独占窗口。

## 按任务读取

- 构建、安装与回退：[内核](../kernel.md)；VM 工作树：[工作区](../workspace.md#构建)；硬件窗口与部署门禁：[部署](deployment.md#内核开发流程与部署门禁)。
- Wi-Fi 固件、WPA3/P2P 与旧候选证据：[主线相关记录](../kernel-mainline.md#相关记录)。
- 内存/拷贝及锁调试配置：[内存拷贝审查](../memory-copy-audit.md)。
- 下游补丁与迁移：[补丁清单](../archive/kernel-patch-inventory.md)（固定审计快照）。
- 电压、thermal、idle 与挂起：[平台 PM 审查](../archive/platform-pm-offline.md)、[板测清单](../parity/platform-pm-board-checklist.md)。
- GPU 功能差距、cooling 与打包验收：[GPU 方案](../gpu-parity-plan.md)。

## 错题

| 触发条件 / 错误 | 原因与正确做法 | 验证入口 |
|---|---|---|
| make C=2退出成功却未执行sparse | 过旧版本会被Makefile警告后跳过；固定工具路径，检查实际CHECK行并拒绝“sparse is not available”日志，不能仅凭退出码 | [uhd4验证](../bringup/2026-10-31-hdr2-uhd4-gate.md) |
| Bifrost一致回边补丁通过MIR/shader-db却在G52挂起 | 同块分支偏移错误把前置块也算入，回跳重置计数器。新增layout回归；主机CFG/静态统计不能代替最终编码和硬件验证。候选先短负载全帧正确、timeout零增量，再测FPS；错误立即否决并正常重启恢复 | [故障隔离与修复](../gpu-loop-repair.md) |
| 向 Ubuntu 根目录直接解内核包，动态程序失效 | tar 替换 /lib 符号链接。安装必须带 --keep-directory-symlink，并保留 Stock 启动项 | [内核安装](../kernel.md)、tools/kernel-install.sh |
| 7.x 更新 Image 后网口模块报 BPF Invalid name，SSH 不通 | 模块的分离 BTF 引用旧 vmlinux 类型 ID；同一 release 和 vermagic 不能证明匹配。更新 Image 时安装同次构建的完整模块集，检查真实加载结果；不要关闭 BTF 掩盖混装 | [HDMI DDC 实测](../bringup/2026-10-19-hdmirx-ddc.md) |
| 回到 5.15 后网口 carrier 正常但收不到包，热解绑／重绑触发 Oops | 厂商网口热重绑路径本次实测会崩溃；保留串口，优先正常重启恢复，不把平台驱动重绑作为通用恢复步骤 | [HDMI DDC 恢复记录](../bringup/2026-10-19-hdmirx-ddc.md#恢复与限制) |
| USB 功能重新绑定后关闭 /dev/hidg*，内核 list_del panic | 5.15 f_hid 同时重置等待队列和仍被打开的 cdev。必须同时修复队列生命周期（dbcef7c1f）与独立 cdev 分配（b86c7e5bd）；只修前者实测仍会崩溃。保留应用保护，重启进入新 Image 才生效 | hid.Reenumerate、tools/hid-rebind-check.py、[内核](../kernel.md) |
| USB 重连期间 SET_ADDRESS 触发 list_add double add | 仅恢复 CRG UDC 的设备状态检查实测仍会 panic。还需登记 gadget.irq，让核心在解绑前同步中断；在锁内检查回调开关，禁用期间不补发 STALL 或处理新 SETUP。继续消费旧完成事件，不直接重置仍被硬件持有的请求链表 | common_drivers/drivers/usb/crg/test_setup_events.py、[CRG 重连](../kernel.md#crg-usb-控制端点重连) |
| 在 FUSE 挂载上 inotify 后守护进程挂死、变僵尸 | 厂商内核为 inotify 发非标准 FUSE_CANONICAL_PATH(2016)；go-fuse v2.8 解析失败不回复，请求永久挂起。FUSE 守护进程必须对未知 opcode 回错误（go-fuse ≥ v2.12；空成功会越界）；卡死时写 /sys/fs/fuse/connections/N/abort 清理 | [NAS 存储与 U 盘](../bringup/2026-10-18-nas-storage-usb-disk.md) |
