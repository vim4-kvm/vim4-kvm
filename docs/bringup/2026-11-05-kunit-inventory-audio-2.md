# 2026-11-05：内核测试清单 audio（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `sound/soc/meson/test_t7_loopback.py`

类型：测试；处置待确认，保留。

原自述：Check real combiner code at channel boundaries and every write failure.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 41 | `C main` | 原检查：Loopback PDM/reference packing, channel boundaries and fault cleanup passed；处置待确认 |

## `sound/soc/meson/test_t7_processing_power.py`

类型：测试；处置待确认，保留。

原自述：Execute real DAPM events, including power-down after failed power-up.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | 原检查：NAME: each power-up failure, repeated power-down and successful retry passed；处置待确认 |

## `sound/soc/meson/test_t7_spdifin.py`

类型：测试；处置待确认，保留。

原自述：Run SPDIF input clock, timer and failure-unwind code without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 49 | `C main` | 原检查：SPDIF seven-rate timers, filter isolation and clock unwind passed；处置待确认 |

## `sound/soc/meson/test_t7_spdifout.py`

类型：测试；处置待确认，保留。

原自述：Execute the SPDIF formatter against old and T7 register layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 45 | `C main` | 原检查：SPDIF lane clearing, mono/stereo and PCM packing passed；处置待确认 |

## `sound/soc/meson/test_t7_tdm_stream.py`

类型：测试；处置待确认，保留。

原自述：Execute stream rollback and trigger error propagation across formatters.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | 原检查：TDM multi-formatter rollback, successful retry and PCM trigger errors passed；处置待确认 |

## `sound/soc/meson/test_t7_tdmin.py`

类型：测试；处置待确认，保留。

原自述：Exercise T7 input slots and actual formatter channel distribution.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | 原检查：TDM slots, mux isolation, legacy layout and channel distribution passed；处置待确认 |
