# T7 GPU 电压、CPU DVFS 与系统 PM 离线候选

结论：未取得可信的 GPU 逐频电压表，保留启动 PWM 电压，不添加
`opp-microvolt`。CPU 两簇四档 bin 与厂商表一致；补 GPU 被动降频绑定、
CPU PSCI idle 描述、风扇 PM 回滚及 Panfrost 恢复错误处理。RX/VDIN/Wave5
仍缺系统上下文恢复，本候选显式拒绝 sleep，不把保护记作恢复能力。
**全程仅开发机与 OrbStack VM，未连接板子、部署、写电压或请求挂起。**
批量窗口和逐项时长见 [上板清单](platform-pm-board-checklist.md)。

2026-10-23 [统一合入](../bringup/2026-10-23-mainline-integration.md)已纳入源码：
CPU power-down idle 在公共 DT 中为 disabled，GPU passive cooling map 仅在显式
`pm-test.dtb` 中出现，两项均**待验证**；既有 critical 温控保留。下文保留原候选
审查与构建快照，所列工作树和旧构建产物在合入后清理；本轮仍未部署或请求挂起。

## 固定来源与候选

| 对象 | 固定提交 / 位置 |
|---|---|
| 正式内核起点 | `1d80e6ccc364161425714c9f7e07f48769b52f41`，fetch 后的 `origin/vim4-kvm-7.3` |
| 候选 | `vim4-platform-pm`，`62724cd3d00ab`；VM `~/src/linux-7.3-platform-pm` |
| 厂商 Linux | `80a07ad5406d57855c996285ae75a50a1b9147ae`，VM `~/src/linux` |
| 厂商 common_drivers | `4cfb128d36f8511b2db1bd13c08d5704347ded49`；T7 与 T7C 都检查 |
| 本轮 U-Boot | `b60ff51ece0fb05456261b1aabb043db6bd923d5`，VM `~/src/u-boot` |
| BL31 | `bl31/bl31_1.3/bin/t7/a311d2/blob-bl31.bin.signed`，SHA256 `2dd34a1000593b9e70324d6a2d9850caa91137ce5c321313a19e3a122cf2e98a` |

本轮 U-Boot 是源码审查对象，不能据此推断板上固件已更新到该提交。
没有移动正式内核分支、更新部署版本锁或改其他任务的工作树。

| 小提交 | 作用与边界 |
|---|---|
| `529c4e5c82f55` | GPU 的 95°C passive trip 关联标准 devfreq cooling；不依赖电压表或虚构功率系数 |
| `15d6103fdefc7` | Panfrost system resume 的 OPP 恢复失败须先返回错误，再决定是否开时钟；含实际 C 函数的 host fixture。此分支仅在声明 `GPU_PM_VREG_OFF` 的 compatible 上执行，T7 当前没有该标志 |
| `39cdded448b26` | 风扇供电关闭失败时同步恢复原输出，包括非 quiet 模式；resume 第一笔新温度绕过睡前的 5% ramp |
| `f642edfad61af` | RX/VDIN 在 PM prepare 阶段拒绝；不再依赖是否加载 CRG 才阻止危险睡眠 |
| `56df2a5bb8041` | Wave5 只对 T7 legacy firmware 拒绝 PM prepare；不改变其他平台既有行为 |
| `62724cd3d00ab` | 八核接入厂商实际 CPU power-down 状态 `0x10000`，使用标准 PSCI cpuidle；不复制占位 system 状态 |

## GPU 电压结论

来源相对路径沿用 [固定证据索引](sources.md)。本轮在固定 V/C/B 下核对：

| 追查路径 | 结果 |
|---|---|
| C `mesont7.dtsi` / `mesont7c.dtsi` 的 GPU `tbl` 与 `mesong12a-bifrost.dtsi` | 实际私有DVFS选择250/400/500/666/800 MHz；各档 `voltage=1150`，没有逐频变化和可靠单位依据 |
| 同两份 DTSI 的 `gpu_opp_table` | 另一张通用表为约285.7/400/500/666.7/800MHz，全部写 `opp-microvolt=<1150>`；285档也与实际tbl的250档不一致。1150µV不是可运行电压，擅自乘1000又超过板级声明范围，不能用该表授予调压资格 |
| V `drivers/gpu/arm/midgard/platform/devicetree/mali_clock.c` | `voltage` 读入结构并打印；适用的时钟切换路径没有消费它来设置 regulator、PWM、SMC 或 SCMI performance domain。厂商配置启用 `MALI_MIDGARD_DVFS`，未启用 `MALI_DEVFREQ` |
| B `board/khadas/configs/kvim4.h`、`board/khadas/kvim4/firmware/timing.c` | 830mV 启动值；700–880mV 的 PWM 编码表是电源初始化换算，不含 GPU 频率、温度、leakage 或 corner 选档关系 |
| B `arch/arm/mach-meson/t7/bl31_apis.c:bl31_get_cornerinfo`、`oscring.c` | 可读 GPU leakage / ring 信息，工具只打印测量字段；未找到用它选择 GPU 电压的实现或映射表。CPU 的 `SM_GET_DVFS_TABLE_INDEX` 不能挪作 GPU bin |
| BL31 | 该 T7/A311D2 文件是签名二进制；当前仓库没有可审查的对应 DVFS/挂起实现。不能把未找到可读表说成固件绝不调压 |
| 7.3 VIM4 DT / Panfrost | 已有 `mali-supply`、PWM regulator 和纯频率 OPP/devfreq；声明范围 700000–922000µV 不是逐频资格证明 |

所以当前证据支持**已检查的厂商 Linux 路径只切频**，不支持给 Panfrost
填写任何逐频微伏值。CPU 电压、启动 830mV、debugfs 推算的 859mV 及常量
1150 均不能代替该表。后续需取得板型/芯片 bin/温度适用范围、频率—微伏表，
以及 PWMAO_E 实际电路标定，再进入 OPP/regulator 调压与实测。
本轮 GPU cooling 只限制已有五个频点；无 Energy Model 时内核使用频率冷却表，
不提供未经标定的瓦数模型。

## CPU、thermal 与风扇对照

对 C 两个 DTSI 的 `a73pwm_opp_table0..3` / `a53pwm_opp_table0..3`，
按频率解析后，与候选 `amlogic-t7.dtsi` 的 `opp-microvolt[-binN]` 比较。
两板型共 16 张表、184 个频压条目，**零差异、无额外频点**；bin 0/1 使用默认值。
A73 12 档 500–2208MHz，A53 11 档 500–2016MHz。
本地原始比较为 `logs/platform-pm-20261023/cpu-opp-comparison.json`。

| 范围 | 厂商 | 7.3 / 处理 |
|---|---|---|
| CPU bin | `meson-cpufreq.c:choose_cpufreq_tables_index` 以 cluster 查询 `GET_DVFS_TABLE_INDEX` | `drivers/cpufreq/amlogic-cpufreq.c` 同一固件命令、每簇选 `binN`，再交给 cpufreq-dt / OPP / PWM regulator；不重复实现 efuse 读取 |
| A73 顶档 / bin 0,1 / 2 / 3 | 2208MHz，1009 / 969 / 919mV | 相同 |
| A53 顶档 / bin 0,1 / 2 / 3 | 2016MHz，1009 / 949 / 919mV | 相同 |
| CPU trip | 95°C switch-on、105°C control、115°C critical；control 映射 A73 0–6 / A53 0–5 | 85°C passive 全档、95°C hot、110°C critical，滞回 2°C；更保守。保留保护；真实热稳态吞吐与风扇同条件测，不以升高安全阈值换跑分 |
| GPU trip | 95 / 105 / 115°C，滞回 5 / 5 / 1°C | 相同；本轮补缺失的 95°C devfreq cooling map，五档最高 cooling state 为 4 |
| NNA/VPU/HEVC | 95 / 105 / 115°C | 阈值相同；DDR、GPU core mask、CPU hotplug 等私有 cooling 没有逐项等价验收 |
| 风扇 | MCU 三阈值 60 / 80 / 100°C | 已有安静策略：六区最高有效温度、45°C 起转、60°C 35%、80°C 70%、100°C 100%，未知温度至少 15%；本轮只修 PM 生命周期 |
| 默认 governor（构建配置） | 厂商 `.config` 为 schedutil | 主仓 `uhd1.config` 为 performance；保留正式策略，A/B 必须分默认配置和共同 governor 诊断组，不能声称默认功耗已相等 |
| CPU idle | `0x10000` CPU power-down，entry 4000µs / exit 5000µs / residency 10000µs；另有极大延迟的占位 state 0 | 原 DT 未接 cpuidle 状态；候选只描述前者及 `local-timer-stop`，`entry-method="psci"`；真实中断/定时器恢复和延迟待验 |

CPU 升频前升压、降频后降压由标准 OPP 执行；本轮没有改电压、时钟切换算法、
CPU 最高频率、默认 governor 或已部署风扇曲线。表相同不等于各批次稳定性已验。

## 系统挂起与唤醒缺口

s2idle 经过设备 prepare/suspend/late/noirq，再等待可唤醒中断；deep 额外经过
PSCI `SYSTEM_SUSPEND`。见 [内核 suspend 流程](https://cdn.kernel.org/doc/html/latest/admin-guide/pm/suspend-flows.html)。
`drivers/firmware/psci/psci.c:psci_init_system_suspend` 查询固件 feature 后注册
platform suspend ops；此前的 PSCIv1.0 / deep 菜单只是固件声明，非恢复证据。
CPU cpuidle 的 `CPU_SUSPEND` 也不等于整机 `SYSTEM_SUSPEND`。

| 设备 / 路径（相对候选源码） | 现状与剩余工作 |
|---|---|
| RX / `t7-hdmirx.c` | probe 持 runtime 引用，异步链路/音频检测、PHY/EDID/HPD 仍无完整保存恢复；新增 prepare 拒绝。需先冻结访问、通知 PCM、保存并重建链路资格 |
| VDIN / `t7-vdin-test.c` | 正常 stop 不等于 system sleep；DMA 孤儿/导出引用、vb2 队列、IRQ/worker 及共享 VCBUS 要有统一 quiesce/rebuild。新增 prepare 拒绝，空闲也不伪装可恢复 |
| Wave5 / `wave5-vpu.c` | 已有 runtime 回调和 T7 恢复实现；没有系统实例/队列恢复。新增 legacy prepare 拒绝；不得简单 force runtime suspend 后声称编码流可续 |
| DRM / `meson_drv.c`、`meson_t7_handoff.c` | 原生 DRM 有 mode-config helper suspend/resume；当前固件 handoff 明确 EBUSY。HPD、共享时钟、音频及原生 T7 TX 仍需显示任务验收 |
| ASoC / `sound/soc/meson/`、RX DAI | ASoC 核心提供 PCM suspend/resume，AXG FIFO/DAI 不能替代 RX 外部采样时钟与路由恢复。须验证 TODDR 停 DMA、XRUN/重建顺序和恢复后的实际非静音数据 |
| USB / CRG、`dwc3-meson-g12a.c` | CRG system suspend/freeze/poweroff 仍 EBUSY；parent 会关 PHY/复位。端点 DMA、event/TRB rings、EP0、HID 打开 fd、重枚举和 remote wake 均待完整实现 |
| Panfrost | 已有 system→force runtime PM、job idle 检查、IRQ/时钟/供电恢复；本轮修 OPP 错误传播，不代表 T7 deep jobs/域/PWM 保持已验 |
| MCU 风扇 | 本轮修失败回滚和 resume 后首样本；I²C/供电恢复实测待做 |
| Ethernet / stmmac、phylib | `stmmac_pltfr_pm_ops` 存在；MAC/PHY/WoL、保电与唤醒 IRQ 必须板上逐项验证，SSH 可达不作 PM 证明 |
| Wi-Fi / `brcmfmac/bcmsdh.c` | 有 SDIO freezer/KEEP_POWER/WOWL 及掉电重探测路径；实际固件恢复和唤醒能力未验。本轮仅读源码，不改 Wi-Fi/P2P；后续窗口另协调 |
| genpd / `meson-secure-pwrc.c` | VPU/VI、USB/SDIO/eMMC 临时常开继续保留；SRAM/DDR/DMC/NOC/CCI 固件必需常开另列，不能一概删除。Wave 域已有状态验证，与整机恢复是两件事 |
| PSCI / BL31 | Linux 有标准入口，厂商 PM 另含 0x82000042 mode SMC 和 AO 超时/恢复原因寄存器；闭源 BL31 的 DDR 自刷新、域保存和唤醒路由尚未证明，无依据不新增私有调用 |

| 唤醒来源 | 精确限制 / 下一步 |
|---|---|
| 外置 RTC（rtc0，HYM8563） | VIM4 `rtc@51` 无 interrupts / wakeup-source；驱动 `rtc-hym8563.c` 仅有 IRQ 时申请中断。先确认 INT 接线和 AO/MCU 路由，不能只加 wakeup-source |
| AO 固件计时（rtc1，meson-vrtc） | `rtc@fe010288` 已有 alarm→suspend 写相对秒数，和厂商 PM 的 SYSCTRL_STATUS_REG2 相符；具备候选契约但没有 Linux IRQ，也没有当前 BL31 唤醒证明，优先受控核对该路径 |
| Power / GPIO | Power 为 GPIOD_4 的 gpio-keys-polled；轮询停止后不能唤醒。必须先确认 IRQ 和 AO/secure 固件支持，再改 gpio-keys；ADC Function 同样不是唤醒证明 |
| IR | `meson-ir.c` suspend 关解码器、resume 重建，没有 enable_irq_wake；AO firmware 的遥控码/路由需单独证明 |
| Ethernet / USB | 需 MAC/PHY/AO 与 host/gadget remote-wake 协议逐项证明；不能把各自 runtime 或连接状态当成整机唤醒 |

**看门狗限制：** `drivers/watchdog/meson_gxbb_wdt.c` 的 system suspend 会
stop 活动 watchdog，resume 才 start。已验证的 PID1 30s 喂狗/超时复位只覆盖
该计数器运行时，不能保证通过 watchdog suspend 回调之后的 s2idle/deep 硬锁复位。
本轮没有改此上游策略；真正挂起仍需独立复位手段或经过实测的睡眠期 watchdog 契约。

## 离线验证与交付状态

- 六个新增提交逐个 `checkpatch.pl --strict --no-tree`：0 error / warning / check。
- 风扇实际 C fixture 与 Panfrost 实际 resume C fixture：Mac Clang、VM GCC 通过。
- 两项新增回归都在原始基线触发断言；候选通过。复用维护分支 runner 的 `run_tests`，在本候选执行既有35项离线fixture，35/35；另加Panfrost一项通过。未运行QEMU/KUnit。
- 全部八个 T7 DT（含 AN400、七个 VIM4 profile）的定向 `CHECK_DTBS=y`：GPU、thermal、OPP、CPU idle、PSCI schema 零诊断。
- 完整生产配置 `make O=$HOME/build/kernel-platform-pm -j4 Image dtbs modules`：通过，2334个模块，编译日志零warning/error；olddefconfig后与主仓 `uhd1.config` 零差异，保留DWARF5/BTF。

VM 输出目录 `~/build/kernel-platform-pm`，schema 目录
`~/build/kernel-platform-pm-schema`；使用主仓 `packaging/kernel-edge/uhd1.config`
经 olddefconfig，无板端操作。构建日志在 VM 同级 `kernel-platform-pm-*.log`。
构建缓存曾临时移到VM tmpfs，完成后已回存原输出目录，未清理其他任务目录。
Image / vmlinux / T7 DTB / 全部模块的SHA256记录在输出目录
`platform-pm-artifact-manifest.json`，运行版本信息如下；它们不是板上验收结果：

```text
release: 7.3.0-vim4kvm-uhd1+
build ID: 9087252aa4904fa9432fe72cb93b1fe272f5ab14
config SHA256: 8af98a1fbefdf163c407f9f04bb31372178b8f8d7d6f00f5dff162b930c968bf
Image SHA256: 7e6b2bb4586f25726790247648a5219bb2484fed478bcd75c0dc0e44573e0951
```

候选已推送 [vim4-platform-pm](https://github.com/vim4-kvm/linux/tree/vim4-platform-pm)，
随后按上述默认关闭条件合入源码；未部署，P04/P06/P08/P09/P10 不提升验收状态。
