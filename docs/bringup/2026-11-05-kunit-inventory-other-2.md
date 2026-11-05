# 2026-11-05：内核测试清单 other（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/misc/adla/test_platform.py`

类型：测试；协调暂缓已解除，在合入 debug-splat-fixes 后逐项确认如下。

原自述：Execute the actual platform power functions with fault-injected host APIs.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | B：runtime PM get、clk parent/rate/enable 逐阶段失败必须回滚原 parent、时钟引用、PM usage/semaphore；suspend/resume 重试和 deinit 不泄漏；regulator get/set/enable/action 失败回收一次。交真实 PM/clock/regulator 与标准故障注入，待实板 |
| 144 | `C main` | K：直接测试生产 adlak_range_valid/adlak_fixup_valid 的负数、尾边界、对齐、shift/unit 和溢出安全。V/B：真实 model 的 v1/v2 配置尺寸选择、零计数 INVOKE 复用旧 fixup 数组、零 fixup 不校验无用 offset，与实际命令 emitter 一致；不重建 model/ioctl，交真实 SDK/ioctl 和样本，待实板 |
| 202 | `C main` | B：platform_get_irq_byname 的 EPROBE_DEFER/ENXIO 必须原样传播且不写入 irqline、成功保留真实 IRQ；交 probe 故障注入和实板 IRQ 路径，待实板 |

## `drivers/net/wireless/broadcom/brcm80211/brcmfmac/test_p2p.py`

类型：测试；协调暂缓已解除，在合入 debug-splat-fixes 后逐项确认如下。

原自述：Compile actual P2P request builders against a recording firmware boundary.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 182 | `C main / scan` | K：直接测试真实 brcmf_scan_params_v2_to_v1 的奇/偶信道尾数组及 SSID 对齐转换。V/B：P2P scan V1/V2 选择、完整 wire header、discover/firmware 错误与分配失败不能置 BUSY；真实 nl80211/P2P 及调试注入，待实板 |
| 182 | `C main / discovery` | V/B：销毁 discovery 清 ENABLED、重建重新初始化 wsec；已配 APSTA 不拆已连接 STA；每个 firmware 错误上报且 APSTA 设置失败仍尝试 UP。真实固件/多接口生命周期与标准调试注入，待实板 |
| 182 | `C main / offload` | V/B/F：ARP/ND 控制按 quirk 走 primary，group 地址表仍按自身 BSS；AP 活动时不启 offload；空/满 IPv6 表的 clear/add、v1 长度/填充/操作码与地址正确，clear 失败不能继续 add。真实固件与标准 IPv6/抓包样本，待实板 |
| 182 | `C main / feature policy` | K：capability 查询后的 AUTO credit 选择、显式 fcmode 优先、查询失败/无 proptxstatus 不覆盖、SAE feature_disable 有效；原位提取生产决策，不移动固件查询或 quirk 发布。V/B：芯片/固件版本资格与真实 capability 读取留给实际无线接口，待实板 |

已有 `firmware_kunit.c` 的 NVRAM 三项来自原样合入的 `496597ebdf195`，直接引用并重跑，
不当作上述 P2P 风险已覆盖。PWM/PWM regulator 在基线 87 文件中没有 Python，
不做删除或重复测试；复用 `0a35577b8de28` 的 `pwm-clock-locking` 实际 API 用例。
同控制器 ABBA 仍按 [PWM 锁分析](../pwm-clock-locking.md)保留，迁移不修复该行为。

## `drivers/pmdomain/amlogic/test_secure_pwrc.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Fault the actual secure-domain transition callbacks and polling macro.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 63 | `C main` | B：secure domain SET/GET 的错误传播、有限轮询、失败/拒绝/未知状态、legacy domain 不额外轮询；真实 genpd/SMC 和标准调试注入，虚拟时间不证明掉电 |

## `drivers/thermal/test_khadas_mcu_fan.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise the driver's actual quiet policy, fault handling and work lifecycle.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | K：默认/自定义温度曲线单调性、fault 最小风量且不压低热传感器、紧急/启停绕过渐变和正常步进上限；V/B：六传感器缺失/读取失败、sysfs 阈值事务、regmap 失败、worker 延迟与 suspend/resume 回收，真实 thermal/sysfs 与注入 |

## `drivers/tty/vt/gen_ucs_fallback_table.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。

## `drivers/tty/vt/gen_ucs_recompose_table.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。
