# 内核与驱动

## 架构与约束

内核身份、配方及Mainline与Vendor布局见[主线](../kernel-mainline.md)。
无线固件/配套模块见[源码锁](../../packaging/kernel/sources.toml)；PHY trap固件根因未明，P2P缺真实对端协商/传输验收。
风扇分Linux温控与U-Boot上电测试，后者早于Linux；改温控不会取消上电测试。
[安静风扇/验证入口](../bringup/2026-10-20-edge-quiet-fan.md)、[U-Boot禁用/验证](../bringup/2026-10-17-uboot-quiet-fan.md)。
IR/按键及NOR与eMMC引脚限制见[设备树记录](../bringup/2026-10-21-edge-ir-keys-spinor.md)。
厂商VDIN、vfm_cap、Wave521和CRG驱动见common_drivers；新板DT/安装按[内核](../kernel.md)，保留stock回退，不替换/lib符号链接。
模块替换、initramfs及整包操作均按该文档；构建成功不证明启动、温控、采集或USB通过，硬件回归须独占。

## 按任务读取

- [构建、安装与回退](../kernel.md)、[VM工作树](../workspace.md#构建)、[部署门禁](deployment.md#内核开发流程与部署门禁)。
- [Wi-Fi、WPA3及P2P证据](../kernel-mainline.md#相关记录)。
- [内存、拷贝与锁调试](../memory-copy-audit.md)。
- [下游补丁快照](../archive/kernel-patch-inventory.md)。
- [电压、温控、空闲与挂起审查](../archive/platform-pm-offline.md)、[板测清单](../parity/platform-pm-board-checklist.md)。
- [GPU差距、散热与验收](../gpu-parity-plan.md)。

## 错题

| 触发 | 做法 | 验证 |
|---|---|---|
| debugfs audiobus读触发abort/重启 | 只读也访问未上电MMIO，dump不受head限制；诊断持板锁，只读已审阅具名状态，不盲扫 | [事故](../bringup/2026-10-25-audiobus-read-abort.md) |
| 板NFS loopback挂自己卡死、RESET后无日志 | 服务端放Mac/VM，冻结用docker pause或VM内nft丢包 | [NAS/USB](../bringup/2026-10-18-nas-storage-usb-disk.md) |
| make C=2成功但未跑sparse | 旧版被警告跳过；固定工具、查实际CHECK行，拒绝不可用日志，不只看退出码 | [门禁](../bringup/2026-10-31-hdr2-uhd4-gate.md) |
| Bifrost回边补丁主机通过、G52挂起 | 分支偏移误算前块而重置计数，须加layout回归；CFG和静态统计不能替代最终编码与硬件验证，短负载全帧正确且无新增timeout才测FPS，出错即否决并正常重启 | [修复](../gpu-loop-repair.md) |
| 根目录解包破坏/lib，动态程序失效 | 安装保目录符号链接、留stock启动项，按工具参数 | tools/kernel-install.sh、[内核](../kernel.md) |
| 换Image后模块BTF错、SSH失联 | 分离BTF依赖原vmlinux类型ID，release/vermagic不足；同次构建完整模块、核实际加载，不关BTF掩混装 | [DDC](../bringup/2026-10-19-hdmirx-ddc.md) |
| 回5.15网口carrier正常却不收包 | 热解绑/重绑实测Oops，保留串口、优先正常重启，不作通用恢复 | [恢复限制](../bringup/2026-10-19-hdmirx-ddc.md#恢复与限制) |
| USB重绑后关hidg触发list_del panic | f_hid须同时修队列生命周期与独立cdev，只修前者仍崩；保留应用保护，重启进新Image才生效 | [HID修复/提交](../kernel.md#hid-重新绑定)、tools/hid-rebind-check.py |
| SET_ADDRESS触发double add | 仅UDC状态检查不足；登记gadget.irq使解绑前同步中断，锁内查回调开关，禁用时不补STALL/处理新SETUP；继续消费旧完成事件，不重置硬件仍持有请求链 | common_drivers/drivers/usb/crg/test_setup_events.py、[CRG](../kernel.md#crg-usb-控制端点重连) |
| FUSE上inotify使守护进程挂死/僵尸 | 厂商非标准opcode，旧go-fuse不回复；未知opcode须回错误，空成功会越界；卡死用连接abort清理 | [版本/恢复实测](../bringup/2026-10-18-nas-storage-usb-disk.md) |
