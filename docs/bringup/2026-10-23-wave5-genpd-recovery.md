# 2026-10-23：Wave5 独立电源域复位与固件冷重载（离线候选）

采用 **T7 DOS_WAVE 独立 genpd 关断/上电**，先排空总线，失败则隔离。
实现 PWRC 回读、OFF/ON 确认、冷 INIT、旧实例 EIO 和延期 DMA 回收。
**仅离线候选，未安装或执行复位；真实硬件恢复待显示任务后的窗口确认。**

前置：[硬复位地址冲突审查](2026-10-23-wave5-runtime-recovery.md)、
[隔离实现与十次验收](2026-10-23-wave5-isolation.md)、
[厂商 E03 缺口](../parity/media.md)。合同采用 genpd + PWRC GET/SET，不复用错误的 hw_reset 地址。

## 采用的硬件合同及固定证据

起点 aa2f875；交付前 fetch/rebase 到显示基线 `c1315a95691e`，无冲突。
独立 worktree `/home/deepdream/src/linux-7.3-wave5-runtime-recovery`，分支
[vim4-wave5-runtime-recovery](https://github.com/vim4-kvm/linux/tree/vim4-wave5-runtime-recovery)。
不修改主内核工作树或已部署分支。厂商 Linux=`80a07ad5406d`，
common_drivers（CD）=`4cfb128d36f8`，SDK=`4c38af2b398d`，完整固定版本见前置记录。
以下原始行号按 aa2 / 上述厂商版本；候选函数名为修改后定位入口。

| 合同部分 | 证据 | 采用方式 |
|---|---|---|
| reset 控制器 | CD `mesont7.dtsi:1328,1687–1690`：基址 0xfe002000；`include/dt-bindings/reset/amlogic,meson-t7-reset.h:46–47,155,159,165,180`：DOS_CAPB3=37、DOS=38、NIC3_WAVE=172、NIC3_HCODEC=176、NIC5_VPU=182、VPUTONOC_PIPEL=197 | 未发现可安全单独交给 Wave5 的 IP reset。DOS/桥线涉及共享资源；不新增 resets，不写寄存器地址猜测用途 |
| 厂商 Wave 节点 | CD `arch/arm64/boot/dts/amlogic/mesont7.dtsi:2729–2755` aml_enc：无 resets，power-domains=`PDID_T7_DOS_WAVE`，DOS/VAPB/WAVE_A/B/C 五时钟 | 采用同一子域与时钟归属，保持功能时钟运行到域关断完成 |
| 独立域及父域 | CD `include/dt-bindings/power/t7-pd.h:8–11,46`：HCODEC=2、HEVC=3、VDEC=4、WAVE=5、NIC3=39；`drivers/power/sec_power_domain.c:258` Wave 父域 NIC3 | 只对 Wave 设备做 runtime PM；父域由 genpd 引用管理 |
| 主线对应 | `include/dt-bindings/power/amlogic,t7-pwrc.h`、`drivers/pmdomain/amlogic/meson-secure-pwrc.c:332–338`；Wave DTS `amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dts:46–62` | 主线 DOS_WAVE 同为域 5，父域 NIC3；T7 Wave binding 仍禁止 resets |
| secure firmware API | `drivers/firmware/meson/meson_sm.c:49–50,109–127`：SET=0x82000093、GET=0x82000095；`meson-secure-pwrc.c:57–100` 已用 GET 的 0/on、1/off 语义 | SET 的 C 返回值仅表示命令被调用，不能证明硬件状态。本轮仅对 T7 DOS_WAVE 增加 GET 有界回读；其他域行为保留 |
| runtime PM 与真实域关断 | `drivers/pmdomain/core.c:877–925,1209–1274`：runtime_suspend 可返回 0 而 governor/域关断未完成；OFF 通知在 provider 成功之后发出 | 先清本次 OFF 标记，再 put_sync_suspend；必须收到 OFF。恢复同样必须收到 ON。不能凭 runtime_status=suspended 判断复位成功 |
| 固件路径 | `wave5-vpu.c:209–286` 原 loader/PM，`wave5-vpuapi.c:20–43` init 包装，`wave5-hw.c:472–581,1290–1420` INIT 与 sleep/wake | 原 runtime resume 不是冷重载，T7 甚至提前返回。复用 `wave5_vpu_init()` 的复制/remap/AXI/IRQ/INIT/固件成功检查，避开 PC 非零时只 ReInit 的包装 |
| DMA 停止 | SDK `multiEnc/vpuapi/enc_driver.c:674–794`、`vdi.c:1515–1544`；主线 `wave5_vpu_reset()` checked FIO | 先停止相应总线并等 T7 idle=0x3f，再内部 ON_BOOT reset；未知双核拓扑拒绝。任何失败都不开始电源循环、不释放 DMA |

secure PWRC 的状态回读上限为 10ms、间隔 10µs；这是软件超时预算，不是新猜测的寄存器
时序。GET 失败/负值、状态不转换、SET dispatch 错误均返回失败。代码不声称能中断
一个永不返回的 SMC；SMC 可返回是 Linux 平台电源驱动的既有前提。

## 板端只读补证据

只读查询日志在 `logs/wave5-runtime/` 的 power-readonly、dt-readonly、reset-readonly.log；
未改状态。查询可能处于其他任务窗口，不作为本轮候选或基线验收。

```sh
ssh vim4 'uname -r; sudo cat /sys/kernel/debug/pm_genpd/pm_genpd_summary;
sudo cat /sys/kernel/debug/clk/clk_summary; sudo ls /sys/kernel/debug/reset;
cat /sys/bus/platform/devices/fe310000.video-codec/power/runtime_status'
```

实际摘要：

```text
T7_NIC3       on
  T7_DOS_HCODEC, T7_DOS_HEVC, T7_DOS_VDEC, T7_DOS_WAVE, ...
T7_DOS_WAVE   on
    fe310000.video-codec   active
T7_DOS_VDEC   off-0
T7_DOS_HEVC   on
    fe09a000.temperature-sensor   unsupported
T7_DOS_HCODEC off-0
    fe320000.jpeg-encoder   suspended
```

Wave A/B/C 各有一个 enable/prepare 引用、约 666666656Hz，consumer 为
`video-codec@fe310000`。`/proc/device-tree` 只读解析显示 resets 缺失，
power-domains 原始 cells=`00000015 00000005`，clock-names=`pclk apb axi bpu vce`。
reset debugfs 入口不存在；未读取或写入 /dev/mem。上述证据确认域连接和独占消费者，
不能证明尚未执行的关断、重载和 DMA 恢复。

## 实现与所有权

1. 超时关闭提交入口、屏蔽 IRQ、固定模块/设备引用，发布 recovering=1。
   worker 先 synchronize_irq（轮询模式停 timer/flush work），防止断电后迟到 MMIO。
   worker 先在 irq_lock 下给全部旧队列 queue_error、标记永久 recovery_error、
   complete_all 和单次 job_finish；这一步不拿 dev_lock，避免 STREAMOFF/job_abort 死锁。
2. 随后按 dev_lock→irq_lock→hw_lock 串行恢复。只有持锁的恢复 worker 可绕过隔离
   MMIO 写保护；并发 open 在入口和加入实例列表前都受设备状态与 dev_lock 约束。
3. checked FIO drain + ON_BOOT 内部 reset → pm_runtime_put_sync_suspend →
   确认本次 genpd OFF → pm_runtime_resume_and_get → 确认 ON → 确认 VCPU PC=0 →
   重新复制固件、冷 INIT、检查命令结果 → 清旧 IRQ 原因/FIFO。
4. 固件对象从成功 probe 保存到设备释放，恢复不进行文件系统/用户态 firmware 请求。
   重载的是已验收的同一镜像；不是仅发 WAKEUP。旧 firmware instance id 全部作废，
   旧 fd 始终 EIO/EPOLLERR，成功后只有新 open 能创建新实例。
5. 恢复中的 close 记录 released，保留实例；vb2 的 put/detach/unmap 记录延期操作，
   保留 backing、attachment、mapping 和独立 dma_buf 引用。只有恢复完全成功才回收
   延期操作和已关闭实例；仍打开的旧 fd 在 close 时释放队列，不再向新固件发 DESTROY。
6. 恢复中再次超时只置失败标志，不递归安排复位。失败保留所有权，isolated=1，
   发 `WAVE5_ISOLATED=1`；成功解除临时模块/设备引用，发 `WAVE5_RECOVERED=1`。
   sysfs 新增只读 recovering，isolation_reason/time 保留本次触发原因并在下次故障更新。

同时修复 enc_close 错误路径把 put 写成 resume_and_get 的引用泄漏，防止额外 runtime
引用阻止断电；device_run 把 PM get 放在 irq_lock 内、通过状态检查之后。
shutdown 设置停止标记并排空已排队的恢复工作，禁止启动新的恢复；已经进入的操作遵循
现有有界 FIO/命令等待和 PWRC 回读，不再发 SLEEP。不会反复重试失败的电源循环。
如果外部故障使 SMC 或内核锁永久不返回，不能声称软件超时能保证重启，这是平台级限制。

恢复失败时即使已看到断电，也保守保留 DMA 到重启，不在不确定的失败路径上另做回收。
该策略可能占用 CMA，但不会以内存回收为由冒险重启 DMA。非 T7/解码器没有启用该恢复路径。

## 离线测试与故障注入

测试提取生产 C 函数并用 ASan/UBSan 执行，模型只替代硬件、PM 和外部所有者：

- `drivers/pmdomain/amlogic/test_secure_pwrc.py`：上下电共 12 个状态/失败用例，另验
  未启用回读的其他域；含延迟到位、SET/GET 失败、负值、错误正值、永不转换和截止时间。
- Wave5 `test_recovery.py`：冷重载成功、8 个固件/drain/genpd/PC/INIT 边界失败，
  验证每条路径 PM 引用平衡，以及没有 OFF 时不能 resume/reload；5 个一次性注入用例。
- `test_isolation.py`：scheduler cancel、迟到 IRQ、全部实例错误、关闭竞争、恢复成功回收
  MMAP/export/import 引用、恢复失败不回收、恢复中再次超时、shutdown 前不启动循环。
- `test_encoder_cleanup.py` 增加 close 失败/成功 PM 引用平衡断言；原 32 项生命周期、
  51 项 FIO/reset、几何/profile/intra-refresh 等 Wave5 测试继续通过。

沿用一次性 `timeout_command=256` 模拟正常 PIC ack 后丢失完成；新增
`recovery_fail_step`（0600，默认 0，读取后清零）：1=drain 前失败，2=断电前失败，
3=OFF 后不上电，4=ON 后不重载，5=恢复中再次超时。它们不会给固件真实挂死输入。
失败注入设计为隔离，需要正常重启回基线；成功注入的验收目标是**无需整机重启**重新编码。

Rebase 后提交：`6f1ab4a99e1d4` 电源回读、`39d42b6393f92` 恢复；拓扑保护重放为
`740e2fb4dd9c9`。全套离线测试再次通过，strict checkpatch 1344 行零错误/告警/check；
仅忽略新测试文件的 FILE_PATH_CHANGES 提示（两个目录已有 MAINTAINERS 覆盖）。
主仓 221 项测试通过、6 skipped。离线通过不替代实板 DMA、4K60 或应用自动重开验收。

独立 O=`~/build/kernel-wave5-runtime-recovery`，Mac heavy 锁内运行
`make ARCH=arm64 -j8 Image dtbs modules`：退出 0、无编译告警，2334 模块。
最终 build ID=`65c6d53f978900a9e6df471aa71866f52924e9e3`；源码与产物哈希见
`logs/wave5-runtime/runtime-artifacts.log`，构建日志 `runtime-final-build.log`。

## 显示任务之后的一次性启动计划

采用 [display-once.py](../../packaging/kernel-edge/display-once.py) 和
[第七窗口修正的静态 PID 1](2026-10-23-display-m1-window7.md)重新 prepare。

先确认显示任务释放窗口及届时基线，fetch/rebase/构建完整候选。候选 Image/DTB/完整
模块放根分区私有目录，默认 extlinux、Image、模块和 sources/workspace 锁保持不变。
每组持 Mac board/heavy 双锁，UART 仅在当次 U-Boot RAM 选择候选，不 saveenv。

| 分组 | 预算 | 验证与退出 |
|---|---|---|
| 首次候选 | 15–20 分钟 | 校验 build ID、私有模块 bind、三服务/UDC、基线哈希；单次 PIC 注入，保存 recovering→OFF/ON→恢复日志；新实例编码、旧 fd EIO；约 5 分钟画面/一路编码/HID/无新增告警冒烟 |
| 十次成功恢复 | 25–35 分钟，分两组 | H.264/H.265 交替，动态 4K60，每次注入后**不重启**创建新实例；加入并发 open、双实例、STREAMOFF/close、导入与导出 fd 关闭；记录 CMA/映射和模块引用趋势 |
| 失败兜底 | 15–25 分钟 | 分别注入各失败阶段与再次超时；拒绝新任务、DMA 引用保留、SSH 可用；正常重启回默认基线，确认不被恢复 worker 卡住 |
| 收尾 | 5–10 分钟 | 回到届时固定基线，核对 GNU build ID、one-kvm/manager/monitor active、UDC configured、真实 HID、isolated=0、taint 与默认文件哈希 |

针对性窗口合计约 **60–90 分钟**，分组结束释放锁。本改动涉及电源管理，按
[部署门禁](../subsystems/deployment.md#内核开发流程与部署门禁)，未来合入部署前还需九类
全量回归，另预算约 45–60 分钟；本轮没有执行或授权自动正式部署。
首次硬件电源循环仍需具备 RESET 后备条件：一次性启动保证下次默认项，不保证硬锁时
看门狗一定能复位。任何 idle/GET/OFF/ON/INIT 失败立即停止成功路径，不放宽保护重试。
