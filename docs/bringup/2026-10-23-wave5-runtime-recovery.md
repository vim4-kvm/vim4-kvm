# 2026-10-23：Wave5 运行时硬复位审查（离线，恢复实现受阻）

**没有完成运行时 reset+reload，不能作为恢复候选上板。** 本轮发现厂商
`vpu_multi.c` 的所谓硬复位地址与同版本 T7 设备树、时钟源码冲突：
`0xfe000044 bit28` 映射到 ACODEC 时钟门，而非已确认的 Wave5 reset。
不能照搬，也不能用可选 NULL reset 控制器返回成功作为硬件恢复证明。
实现仅增加复位拓扑保护；现有超时隔离行为保留。未 SSH、安装、重启或合入部署分支，
没有修改 sources.toml/workspace.toml。

前置：[首次恢复审查](2026-10-23-wave5-recovery.md)、
[隔离实现](2026-10-23-wave5-isolation.md)、
[隔离正式验收](2026-10-23-wave5-isolation-final.md)、
[厂商能力对照 E03](../parity/media.md)。

## 固定源码与分支

两次 fetch 后 `origin/vim4-kvm-7.3` 均为
`aa2f875bec2fc7c9a4952fccb9dcaa6fbfc4aa64`，尚无采集稳定性合入增量。
新独立 worktree `/home/deepdream/src/linux-7.3-wave5-runtime-recovery`，
分支 [vim4-wave5-runtime-recovery](https://github.com/vim4-kvm/linux/tree/vim4-wave5-runtime-recovery)。
没有切换或修改原内核工作树。下表主线位置按 aa2f875，厂商位置按：

- Linux 5.15 `80a07ad5406d57855c996285ae75a50a1b9147ae`。
- common_drivers `4cfb128d36f8511b2db1bd13c08d5704347ded49`，下文简称 CD。
- encoder_libs_aml SDK `4c38af2b398d00a906c26aa166d630a9f73d3f9e`，路径前缀 `multiEnc/`。

## 复位与重载映射

主线驱动路径前缀 `drivers/media/platform/chips-media/wave5/`；CD 编码器路径前缀
`drivers/media_modules/frame_sink/encoder/multi/`。以下为源码审查，不是硬件执行结果。

| 阶段 | 厂商证据 | 主线映射与边界 |
|---|---|---|
| 时钟与上电 | CD `vpu_multi.c:313–339` 先使能 DOS/APB/A/B/C，再 `vdec_poweron(VDEC_WAVE)`，延时，再调用 hw_reset | `wave5-vpu.c:340–364` 的 clk_bulk、pm_runtime、reset 控制器；T7 保持 probe 的 runtime 引用，不能假设另一次 put 就使电源域关闭 |
| 电源域归属 | CD `drivers/power/sec_power_domain.c:258` DOS_WAVE 的父域 NIC3 | `drivers/pmdomain/amlogic/meson-secure-pwrc.c:69–100,338` 经 SM_A1_PWRC_SET 控制 DOS_WAVE/NIC3；SMC 返回成功不能单独证明挂死 DMA 已排空 |
| 超时 | CD `vpu_multi.c:1390–1401` IRQ 有界；SDK `vpuapi/include/vpuconfig.h:77–79` busy/编码超时 | `wave5-hw.c:209–228` 命令轮询；`wave5-isolation.c` watchdog/job_abort/隔离。现有注入是正常命令 ack 后模拟超时，不使固件真的挂死 |
| 总线停止 | SDK `vpuapi/enc_driver.c:674–746` 按 CONFIG0 backbone/vcore 与 CONFIG1 bit26 双核分支停止；`vdi.c:1515–1544` Wave521C idle=`0x3f` | `wave5-hw.c:1422` reset 使用 checked FIO、idle 轮询。原实现没有 legacy 双核 VCORE1 排空，本轮在任何写操作前拒绝该拓扑 |
| 内部软复位 | SDK `enc_driver.c:749–794` SAFETY 要先 SLEEP，RESET_REQ/STATUS 后解除 stop，FORCE/SAFETY 再 WAKEUP | ON_BOOT 不发 SLEEP/WAKEUP，可作为后续冷初始化的内部复位基础；SAFETY 不适合 SLEEP 本身不响应的挂死。mask SDK=`0x0fffffff`，T7 resume/主线=`0x07ffffff`，bit27 含义仍未确认 |
| 外部硬复位 | CD `vpu_multi.c:980–1006` 直接写 `0xfe000044 bit28`；`:436–440,1863–1866` RESET ioctl 实际空操作 | **无可靠映射**，见下一节。当前 T7 binding 禁止 resets，不能给它新增 NIC3 桥 reset 来冒充 IP reset |
| 固件冷加载 | SDK `enc_driver.c:274–355` 写 common memory、remap/code/temp/AXI/IRQ、INIT_VPU/CORE_START | `wave5-vpu.c:209–240` request_firmware；`wave5-hw.c:472–581` 复制固件及初始化。必须先停止旧固件取指/DMA，不能在运行中的 common memory 上覆盖代码 |
| 固件唤醒/重初始化 | SDK `enc_driver.c:573–661` WAKEUP 使用旧 common memory；CD `vpu_multi.c:3421–3467` resume reset/remap/INIT；SDK ReInit 只在 code base 变化时重新写固件 | `wave5-vpuapi.c:20–43` 若 PC 非零走 ReInit 并返回 EBUSY；不能直接把 probe loader 再调用一次当作冷重载。WAKEUP 不等于重新加载固件 |

## 硬复位地址冲突：不能依据函数名移植

完整地址推导如下，全部来自上述固定 CD 版本：

1. `arch/arm64/boot/dts/amlogic/mesont7.dtsi:1328` 把外设总线映射到 `0xfe000000`；
   `:1330–1337` 时钟控制器 basic 资源位于偏移 0，覆盖 `0x49c` 字节。
2. 同文件 `:1687–1690` reset 控制器位于偏移 `0x2000`，实际基址 **0xfe002000**。
3. `drivers/reset/reset-meson.c:47–66,110–113` 的 T7 level offset=`0x40`，
   bank=`id/32`、bit=`id%32`。RESET1_LEVEL 应在 **0xfe002044**。
4. `drivers/clk/meson/t7.h:25` 定义 `CLKCTRL_SYS_CLK_EN0_REG0=(0x11<<2)`；
   `drivers/clk/meson/t7.c:7148` 将其 bit28 定义为 **t7_acodec**。
   这才与 `vpu_multi.c:980` 的 **0xfe000044** 物理地址一致。
5. 即便擅自把地址“修正”为 0xfe002044，bit28 也会是 reset id60；
   `include/dt-bindings/reset/amlogic,meson-t7-reset.h:69` 命名为
   `RESET_MIPI_DSI1_PHY`。`RESET_BRG_NIC3_WAVE` 是同文件 `:155` 的 id172，
   对应 0xfe002054 bit12，三者不能互换。

因此首次审查记录把该函数称为“真正的硬复位”过于确定；本记录修正该结论。
本轮工作过程中的“bit28 就是 NIC3 桥”和忽略控制器基址的 id60 推断也已撤回。
目前证据只能证明厂商函数写了什么，不能证明它实际复位 Wave5。

7.3 `arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi:527–532,576–579` 同样使用上述总线与
reset 基址；`Documentation/devicetree/bindings/media/cnm,wave521c.yaml:78` 明确
`resets: false`。Wave5 DTS `amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dts:46–62`
只声明 DOS_WAVE 电源域与五个时钟。既往
[卸载事故](2026-10-19-wave521-uhd.md#恢复及未覆盖范围)已经证明不能把 NIC3 桥随意交给编码器。

要解除阻塞，需要 T7 专用 IP reset 的准确寄存器/控制器归属，或 secure firmware 的
DOS_WAVE 断电/上电合同：包括旧 AXI outstanding 处理、父 NIC3 的共享影响、超时与
失败状态、重新访问 MMIO 的条件。现有 U-Boot 树的 bl31 目录只有 bin 分发内容，
本轮未找到该电源序列的可审查实现。没有反汇编固件，也没有用实板试写来猜测。

## 本轮代码及离线验收

只修改 `wave5-hw.c` 和 `test_reset.py`：legacy CONFIG1 bit26 表示双 VCORE，现有
reset 只排空 VCORE0，新增 `-EOPNOTSUPP` 拒绝；发生在 BUSY/FIO/RESET_REQ 写入之前。
非 legacy ABI 不套用这个 bit 的解释。没有新增恢复模块参数或未接线的恢复函数。

严格 checkpatch：`0 errors, 0 warnings, 0 checks, 53 lines checked`；diff check 通过。
实际 C + 内核 iopoll 宏的 ASan/UBSan MMIO 测试由 47 增至 **51 项**：新增三种 reset mode
对双核拓扑的零写入拒绝，以及非 legacy 不误拒绝。既有迟到/永不 idle、FIO 读写失败、
reset status 不清、SLEEP/WAKEUP 拒绝/超时继续通过；所有 Wave5 test_*.py 通过。
现有隔离状态机测试通过，但**未新增或宣称通过 runtime reload 成功/失败/再次超时测试**，
因为对应生产路径尚未实现；MMIO mock 也不构成物理 DMA 停止证明。

内核提交 `bf72f23eda579c08798794579491ace721a742ee`，已推送上述功能分支。
独立 O=`/home/deepdream/build/kernel-wave5-runtime-recovery`，从 aa2 完整构建输出复制
`.config`、Module.symvers、vmlinux，运行 olddefconfig/modules_prepare 后，仅编译 Wave5 模块：

```sh
/usr/bin/lockf -t 600 /tmp/vim4-heavy.lock orb -m vim4-build bash -c '
make -C /home/deepdream/src/linux-7.3-wave5-runtime-recovery \
  O=/home/deepdream/build/kernel-wave5-runtime-recovery ARCH=arm64 -j8 \
  M=/home/deepdream/src/linux-7.3-wave5-runtime-recovery/drivers/media/platform/chips-media/wave5 \
  MO=/home/deepdream/build/kernel-wave5-runtime-recovery/wave5 modules'
```

实际退出 0，含 MODPOST、LD、BTF，无 warning/error。模块 build ID
`2337cd64840ef1db888b61c05fe168c5b4f0f03a`，SHA256
`7d4b91be2f273678838671d3ca929a9f124642610f56b7cd154eb7fed894d5d2`。
**没有构建完整候选 Image/DTB/modules 发布包，不能拿此模块混装上板。**
日志位于忽略目录 `logs/wave5-runtime/`。
主仓 `python3 -m unittest discover -s tests -p 'test_*.py'`：221 项，6 skipped，OK。
第一次因旧审查记录新增说明超过 12000 字节而失败，改为就地纠正原表格后复测通过。

## 后续运行时所有权设计要求（未实现）

必须区分 RUNNING、RECOVERING、ISOLATED；超时先拒绝新 open/提交，所有旧实例报错。
固件冷重载后原 instance id 不再有效，旧 fd 必须一直返回 EIO，只让新 fd 创建新实例。
不能恢复后简单清掉现有 isolated 标志：隔离 close 已丢弃 file 关联而保留 instance，
vb2 wrapper 的 put/detach/unmap 也可能被跳过。需要记录延期回收，确认 DMA 停止后
按一次所有权回收，覆盖 MMAP/export/import、STREAMOFF 和 close 与 worker 并发。

隔离 worker 当前只取 irq_lock，刻意不取 dev_lock，因为 STREAMOFF 可持后者等待
job_abort。恢复必须先结束 scheduler 等待，再有序序列化 dev/irq/hw 锁，并防止旧 IRQ
报告落到新固件实例。第二次超时应使当前恢复失败而不是递归安排复位；任何 DMA 停止
证据缺失均保留内存和电源，回退现有隔离。模块/设备引用也须在成功回收后平衡。
shutdown/remove 不能因等待恢复 worker 或固件而新增无界等待。

## 后续上板计划与窗口预算（本轮不执行）

当前分支只有拓扑保护，**不安排恢复验收窗口**。先解决硬件合同并完成上述生产路径、
故障状态机测试和完整 Image/DTB/modules 构建，再按
[一次性启动安全网](2026-10-23-display-m1-safety.md)申请窗口。

| 分组 | 预计独占时间 | 门禁与退出 |
|---|---|---|
| 基线副本一次性启动验证 | 10–15 分钟 | 固定届时真实基线；UART sysboot 从根 ext4 读取基线副本，再重启验证默认项。若 B 已验收同样路径，复用其证据并核对版本 |
| 候选首次启动及一次软件注入 | 15–20 分钟 | prepare/stage 私有目录，U-Boot RAM 中 sysboot；验证模块 bind、4K60、EIO、并发 open、重载后新实例；失败即停止 |
| 十次注入及新实例恢复 | 25–35 分钟 | 分两组各五次，H.264/H.265 交替，含多实例、close/STREAMOFF 竞争；每次恢复后测动态 4K60、SSH、taint、内存引用，无真实挂死输入 |
| 失败兜底及 KVM 回归 | 15–25 分钟 | 受控注入复位失败/重载失败/恢复中再次超时；确认隔离、有限时关机；回到默认基线，核对服务、UDC 和真实 HID |

合计约 **65–95 分钟**，各组分别持 Mac board/heavy 双锁，结束释放；包含恢复基线预算，
不包含硬件故障排查。每次进入候选前重新确认基线未被其他任务更新。
使用 `packaging/kernel-edge/display-once.py prepare --payload … --init … --baseline … --output …`
离线生成候选；双锁下 `stage candidate.tar` 只暂存私有目录，然后 UART 当次 sysboot。
不覆盖默认 Image/DTB/模块，不 saveenv，不改正式锁。仅 `panic=20` 不能保证硬件硬锁复位，
未来首次真正硬复位测试仍需现场 RESET 条件；一次性启动只保护下次默认启动。

本轮没有板端命令或恢复基线证据：从未进入候选，不能把历史 4K60/十次隔离验收当成本轮恢复通过。
