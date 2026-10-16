# 2026-10-16：CRG EP0 重复入队导致重启

PiKVM 延迟对照期间切换应用后发生非计划重启。板载 pstore 保存了
`list_add double add → build_ep0_status → setaddressrequest → crg_handle_setup_pkt`
的首个 BUG，随后 `Kernel panic - not syncing`；下一次启动参数含
`reboot_mode=kernel_panic`。显示驱动的 vblank 警告位于异常展开路径，不能据此
把根因归到编码器或显示。此前没有执行 reboot、刷机或内核部署。

只恢复 RECONNECTING 状态下的 SETUP 检查仍不足：第一次修订在 HID 重绑定
测试完成 55 次后再次沿同一路径 panic。继续审查发现驱动没有设置 `gadget.irq`，
USB 核心解绑前的 `synchronize_irq()` 因而被跳过；原 SETUP 处理在释放锁后
检查 async 开关，并在关闭时重新加锁补发 STALL，可跨过控制器重置留下请求。
最终修订登记 IRQ、串行化回调开关与设备状态、在锁内提前拒绝禁用期间的新
SETUP，并保护 disconnect 回调；保留旧传输完成事件的消费及原有复位清理。

源码修复为 common_drivers `9493ab5ee` + `11d7ea196`，CI 接入为 `4cfb128d3`。
事件分派回归直接编译生产函数：原始代码与第一版均在对应负例失败，最终版在
macOS 与 ARM64 Linux 通过。ARM64 模块构建通过，候选与板上原模块的导入符号
CRC 完全一致。仅安装 `amlogic-usb.ko` 并重建 initramfs，未替换 Image、设备树
或其他模块；已受控重启并以运行模块 build ID 确认生效。
最终模块 SHA-256：`6b7b086793d56ddd94276d7f36439f2ac50bd2a9b7c4d06ae0e155fc1447bb71`。
旧模块和 initramfs 保存在板上 `/var/backups/vim4-usb-20261016/`；内核 deb 的版本
仍为原安装版本，本次属于有备份的单模块修复，后续内核包由固定源码清单构建。

证据目录：`logs/reboot-20261016/`，保留两次 panic、负例、编译、安装及硬件测试日志。

最终模块上连续三轮各 100 次 HID 重绑定通过，测试保持三个 HID fd 注册在 epoll
中跨越解绑/重绑，核对主机 configured 后注销并关闭。启动 ID 始终为
`9ac9de0a-1b7f-44fe-934e-c9d8e40ed5d0`。随后 PiKVM、One-KVM、NanoKVM、JetKVM
各完成一次服务 active、HTTP 可达、USB configured 检查。计划中的第二轮切回
PiKVM 被虚拟介质保护正常阻止：NanoKVM 已自动挂载共享 `disk.img`；未强制弹出，
因此不把计划的 13 次轮换记为通过。恢复 One-KVM，保留共享介质与原 EDID。
本轮没有验证物理按键到画面的延迟或长时间视频质量；300 次无复现也不是永久
稳定性保证。后续低延迟测试应继续监控 pstore 与启动 ID。
