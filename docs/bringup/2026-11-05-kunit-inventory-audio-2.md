# 2026-11-05：内核测试清单 audio（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `sound/soc/meson/test_t7_loopback.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Check real combiner code at channel boundaries and every write failure.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 41 | `C main` | V/B/F：PDM/reference 通道掩码与 combiner 同步、无效 source 拒绝、每次写失败清理；真实 ALSA loopback 与样本 |

## `sound/soc/meson/test_t7_processing_power.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute real DAPM events, including power-down after failed power-up.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | B：DAPM power-up 各阶段失败、重复 power-down 幂等、恢复重试、clock 引用/独占率和 cache_only 平衡；真实 DAPM 和标准调试注入 |

## `sound/soc/meson/test_t7_spdifin.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Run SPDIF input clock, timer and failure-unwind code without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 49 | `C main` | V/B：七种 PCM rate 的检测 timer、filter 隔离、probe 每阶段失败的 pclk/refclk 回收；标准 SPDIF/ALSA 与时钟调试 |

## `sound/soc/meson/test_t7_spdifout.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute the SPDIF formatter against old and T7 register layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 45 | `C main` | V/B/F：legacy/T7 lane 清除、mono/stereo 与 PCM bit packing、非法格式拒绝不改寄存器；ALSA 样本/标准 loopback |

## `sound/soc/meson/test_t7_tdm_stream.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute stream rollback and trigger error propagation across formatters.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | V/B：多 formatter start 中途失败全部 rollback、成功重试、STOP 与 trigger 错误传播；真实 PCM/DAPM 与注入 |

## `sound/soc/meson/test_t7_tdmin.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise T7 input slots and actual formatter channel distribution.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | V/B：slots/channel 掩码、mux 无关位、legacy/T7 格式、通道分布和 invalid 拒绝；标准 PCM/TDM 与寄存器调试 |
