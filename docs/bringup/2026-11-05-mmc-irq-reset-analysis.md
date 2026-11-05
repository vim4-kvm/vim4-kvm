# 2026-11-05：MMC 硬中断锁修复与冷复位分析

联合候选 `.23` 的 Invalid wait context 已定位并离线修复，提交
`f911e1d8817fb1ebab4acf94ed96ddf9404e193c`。两次意外 cold_boot 的原因仍未明，
只记录证据和下一窗口采集要求，没有猜测性修改 PD、看门狗或复位策略。
本轮没有上板，未运行候选；实板结果仍以[联合记录](2026-11-05-vdec-joint-debug.md)为准。

## MMC 根因与修复

原串口 `logs/hwdecode-parity-r33b/uart-1793865297808564000.log:859` 起，
当前任务副本在 `build/debug-splat-fixes/followup/r33b-uart.log`。
4.805574 秒的报告在 swapper/0 的硬 IRQ 栈中获取 dma_entry_hash 的 normal spinlock：
`debug_dma_unmap_sg → dma_unmap_sg_attrs → meson_mmc_post_req → meson_mmc_irq`。
`context-{2:2}` 与目标 `{3:3}` 对应 raw 和可配置的锁等待类别，不是 DMA 段长错误。

`kernel/irq/handle.c:__handle_irq_event_percpu()` 不把 IRQF_ONESHOT 主处理函数
标为可强制线程化；驱动 `request_threaded_irq()` 的主函数仍执行在硬 IRQ。
`CONFIG_PROVE_RAW_LOCK_NESTING=y` 因而发现 DMA debug 的 spinlock_t 不适用于
此处。下游提交 `52b95c8493264` 把终端请求提前在主函数完成，实际还会执行
bounce DMA sync 或 driver-owned SG 的 post_req/unmap，并非仅通知 MMC core。

修复位于 `drivers/mmc/host/meson-gx-mmc.c`：

- `:1114` 完成分支恢复 IRQ_WAKE_THREAD；sync、unmap、request_done 都在既有
  `meson_mmc_irq_thread()` 中执行，不改变 descriptor 停止、错误轮询和后续命令顺序。
- `:186`、`:1078`、`:1240`、`:1371` 将 SDIO IRQ-enable 寄存器锁及全部配对操作
  改成 raw_spinlock。该锁确实由同一个主处理函数获取，保留 normal spinlock
  会留下另一处同类错误。临界区只有 MMIO 和 IRQ-safe 的 SDIO work 排队，没有
  DMA 调用、分配或睡眠轮询，符合硬 IRQ 的实际需求。
- 保留 IRQF_ONESHOT，避免主函数与线程并发；没有关闭调试配置、改 lockdep
  类别或将 DMA debug 全局锁随意 raw 化。

代价是撤回简单请求在硬 IRQ 完成的调度优化，Wi-Fi 性能须后续复验，本轮不作性能
结论。没有可抽取的纯逻辑；不以寄存器/DMA mock 代替真实 IRQ 上下文验证。

### 上游核对

查阅[主线 MMC](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/mmc/host/meson-gx-mmc.c)、
[linux-next](https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git/tree/drivers/mmc/host/meson-gx-mmc.c)、
[MMC next](https://git.kernel.org/pub/scm/linux/kernel/git/ulfh/mmc.git/tree/drivers/mmc/host/meson-gx-mmc.c?h=next)：
完成分支均直接唤醒线程，但 SDIO 锁仍为 spinlock_t，没有对应的完整修复可移植。
[DMA 维护者树](https://git.kernel.org/pub/scm/linux/kernel/git/mszyprowski/linux.git/tree/kernel/dma/debug.c?h=dma-mapping-for-next)
的 dma-mapping-for-next（`0d584f9143d8de202bb297e8e65c2db927281695`）和 fixes
（`6628e7d4c6b25c8d18f1345e3a20d21829aae7e4`），以及主线/next 的 DMA bucket
仍用 normal spinlock。lore 的 meson/Invalid wait、dma-debug/hardirq/raw-lock
检索未找到适用修复。因此本次为自写修复；未把一般性的 radix_lock 死锁修复误当
成本问题补丁。检索快照保存在 `build/debug-splat-fixes/followup/`。

## 两次冷复位的共同证据及限度

| 证据 | 首轮 RAM | 联合 `.23` |
|---|---|---|
| 串口 | `logs/hwdecode-parity/uart-1793805175739342000.log` | 上述 r33b 串口 |
| 最后一条内核时戳 | 5.522427 秒；gadget 启动消息附近 | 17.999480 秒；BCM43752 固件初始化成功 |
| 下一次 ROM 标记 | 第 1158 行 `T7:BL...POC:CF;...OVD:0` | 第 1118 行相同标记 |
| BL31/固件输出 | 第 1278 行 reboot reason 0x00 | 第 1238 行 reboot reason 0x00 |
| AOCPU sticky / U-Boot | 第 1366 行 0x0，后续 cold_boot | 第 1328 行 0x0，后续 cold_boot |
| 重启后的 PD 快照 | flags=41，5V/1.5A，RDO 14019096 | 相同字段 |
| panic / 正常关机过程 | 意外复位前均未记录到 | 意外复位前均未记录到 |

串口没有逐行主机单调时戳。最后内核消息后可能还有静默间隔，不能把这两条时戳
当作复位发生时间，也不能用它们小于 30 秒排除看门狗或 panic=20。
首次用户确认供电线、主机和 RESET 未动，见[首轮记录](2026-11-04-hwdecode-parity.md#首轮-ram-窗口)；
不能从 cold_boot 标签反推人为拔线。

只读核对 U-Boot `4317387a6a58f4d42186cbadc24cd3cc52675bc3` 的
`cmd/amlogic/cmd_reboot.c:do_get_rebootmode()`：从 AO_SEC_SD_CFG15 的
bit 12 起提取 reboot mode；若原值为 cold 且 AOCPU sticky 为 watchdog(13)，
会改显示 watchdog_reboot。T7 的寄存器别名来自 soc_def.h / register.h，地址为
`0xfe01037c`。sticky 则由 `arch/arm/mach-meson/t7/stick_mem.c` 经 mailbox 取得，
不是这个寄存器中的另一组硬件故障位。没有改动该 U-Boot 工作树。

两段串口中，候选**之前的受控重启**也打印 reboot reason 0x00，但 sticky 为 0xd，
并显示 watchdog_reboot；异常后 sticky 为 0。可见 0x00 本身不区分这些复位。
ROM 的 POC/OVD 标签也没有已核实的本板故障位解码，不能把 OVD:0 当作排除欠压。

- 看门狗：PID1 都声明 Meson GXBB、timeout=30s。驱动
  `drivers/watchdog/meson_gxbb_wdt.c` 会设定时基/超时、ping，并支持 timeleft；
  没有提供能独立区分这些复位的 bootstatus 硬件解码。当前缺故障前喂狗/剩余时间
  的连续记录，不能仅凭 sticky=0 或 sysfs bootstatus=0 排除看门狗。
- lockdep：`kernel/locking/lockdep.c:print_lock_invalid_wait_context()` 关闭
  debug_locks、打印并返回，不直接 panic/reboot；后续 Linux 仍运行到固件初始化。
  这不证明它与复位无关，但不能把标题里的 BUG 当作已发生 panic 的证据。
- PD/供电：本板 USB-C 单线供电，TCPM 的 HARD_RESET_SEND 路径明确警告非自供电
  sink 可能掉电；收到的 Hard_Reset 也可能先于 Linux 充分打印。现有串口没有
  对应协议日志，重启后的 5V/1.5A 快照不能证明故障前合同或 VBUS 波形。
  这是一条需采证的机制，尚不是原因判定；不修改标准 PD 恢复、CPU 电压或 watchdog。

## 下一窗口采集与判定

本轮不新占板：现有串口已复现锁错误，冷复位先给采证方案。若后续由本任务执行
窗口，须先把具体候选 build ID、完整可执行窗口脚本、恢复 proof 与判定写入结果
文件，再在 who=hwdecode-parity 的票之后申请；本节不是已执行或已就绪的窗口脚本。
每次仅 RAM 一次启动，目标 15 分钟、上限 30 分钟，首错停止，结束恢复正式 `.3`
并完成身份/受保护文件、UDC/服务和真实接收视频核验；不接触 HEVC 草稿或 PWM debugfs。

下次一次窗口应同时取得以下证据，避免逐项试错重启：

1. 主机 UART 从基线开始到恢复全程采集，每个收到的数据块同时记录 UTC 和单调
   时戳；保存原始字节，明确无字节间隔，才能比较最后 Linux 输出至 ROM 重启的时长。
2. 私有 RAM init 在 exec systemd 前准备有界软件日志采集，首 60 秒输出到 UART，
   不等 SSH 就绪：读取 `/sys/kernel/debug/usb/fusb302-*/log` 与 `tcpm-*/log`，
   记录 Soft_Reset、Request/Accept/PS_RDY、Hard_Reset 发送/接收及 VBUS/CC 事件。
   这是驱动软件 ring，不从用户态读 FUSB302 的 read-to-clear IRQ 寄存器，不抢 I²C。
3. 同步采集 watchdog 的 identity/state/timeout/timeleft/status/bootstatus、PID1
   RuntimeWatchdogUSec，以及 Type-C / tcpm-source-psy 的角色、online、电压/电流。
   记录属性不存在/读取失败；不打开 /dev/watchdog、不主动喂狗、不改超时。
4. 首次可读时备份 pstore，自动返回 `.3` 后立即取 `/sys/fs/pstore`、
   `/var/lib/systemd/pstore` 和前一 boot 的 journal；明确 systemd-pstore 是否已搬移。
   pstore 为空不能单独排除掉电或 panic。
5. U-Boot 中只读记录完整 reboot/sticky/PD 输出及 AO_SEC_SD_CFG15 原值；若要
   增加早于现有解释逻辑的打印，先离线准备并审阅，不能在窗口临时改写引导器。
   不运行任意 devmem 扫描，不读未确认上电的 MMIO。
6. 如软件记录仍不能区分 VBUS 掉电与复位输入，下一步需有同一时间轴的外部 VBUS/
   RESET 采样或 PD 分析仪；没有这些输入时保留“未明”，不猜改软件。

MMC 判定：保持 DMA_API_DEBUG、PROVE_RAW_LOCK_NESTING 开启，eMMC 挂载与有界
只读 direct I/O、Wi-Fi 固件/SDIO 路径均完成，无 Invalid wait context、DMA/KASAN/
lockdep 告警，确认 lockdep 仍开启。必要时用函数过滤的 trace 证明 DMA completion
来自 IRQ 线程。新候选若再回 BL2，先保全上述数据，不开始解码、不第二次重试。

## 离线验证

strict checkpatch 为 0 error/warning/check；模块配置明确
MMC_MESON_GX=m、PROVE_RAW_LOCK_NESTING=y；内建为 y。W=1+C=2 用指定 sparse
`v0.6.5-rc1-21-g84ec0658` 实际出现 CHECK，三个配置的修改文件均无诊断；未修改的
arm64 vgetrandom 声明诊断保留。模块链接、完整生产 Image/modules/dtbs 退出码 0。
没有修改头文件、binding 或调试配置，没有新增模拟 IRQ/DMA 的单测；smatch 不可用。
命令及原始输出：`build/debug-splat-fixes/followup/mmc-builds.log`，VM 输出仍在
`/home/deepdream/build/debug-splat-fixes/`。生产 Image SHA-256：
`3c7e2df1a470b4e02fc6d058b29c5a9f8fb5e16fac158944194e01fbd05eb05e`。
