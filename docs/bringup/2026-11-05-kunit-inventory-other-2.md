# 2026-11-05：内核测试清单 other（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/misc/adla/test_platform.py`

类型：测试；处置待确认，保留。

原自述：Execute the actual platform power functions with fault-injected host APIs.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | 待确认：核对内嵌 C 的断言 |
| 144 | `C main` | 待确认：核对内嵌 C 的断言 |
| 202 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/net/wireless/broadcom/brcm80211/brcmfmac/test_p2p.py`

类型：测试；处置待确认，保留。

原自述：Compile actual P2P request builders against a recording firmware boundary.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 182 | `C main` | 原检查：P2P scan ABI, lifecycle, offload routing and TX credit policy passed；处置待确认 |

## `drivers/pmdomain/amlogic/test_secure_pwrc.py`

类型：测试；处置待确认，保留。

原自述：Fault the actual secure-domain transition callbacks and polling macro.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 63 | `C main` | 原检查：Secure PWRC: 12 transition/failure cases and unmodified-domain behavior passed；处置待确认 |

## `drivers/thermal/test_khadas_mcu_fan.py`

类型：测试；处置待确认，保留。

原自述：Exercise the driver's actual quiet policy, fault handling and work lifecycle.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | 原检查：Khadas quiet fan policy, faults and lifecycle: PASS；处置待确认 |

## `drivers/tty/vt/gen_ucs_fallback_table.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。

## `drivers/tty/vt/gen_ucs_recompose_table.py`

类型：源码生成工具（上游，保留，不属于项目测试迁移）。
