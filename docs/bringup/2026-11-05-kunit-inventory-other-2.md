# 2026-11-05：内核测试清单 other（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/misc/adla/test_platform.py`

类型：测试；协调暂缓，保留原文件；待 t48 确认后再审风险和迁移，避免与启动 splat 修复冲突。

原自述：Execute the actual platform power functions with fault-injected host APIs.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | 待确认：核对内嵌 C 的断言 |
| 144 | `C main` | 待确认：核对内嵌 C 的断言 |
| 202 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/net/wireless/broadcom/brcm80211/brcmfmac/test_p2p.py`

类型：测试；协调暂缓，保留原文件；待 t48 确认后再审风险和迁移，避免与启动 splat 修复冲突。

原自述：Compile actual P2P request builders against a recording firmware boundary.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 182 | `C main` | 原检查：P2P scan ABI, lifecycle, offload routing and TX credit policy passed；处置待确认 |

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
