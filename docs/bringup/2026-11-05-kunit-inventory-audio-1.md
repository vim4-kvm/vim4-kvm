# 2026-11-05：内核测试清单 audio（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `sound/soc/meson/test_t7_aed.py`

类型：测试；处置待确认，保留。

原自述：Execute the real AED SRAM, biquad validation and enable/failure sequence.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | 原检查：AED dual SRAM, stable biquads, FIFO source isolation and every failure passed；处置待确认 |

## `sound/soc/meson/test_t7_asrc.py`

类型：测试；处置待确认，保留。

原自述：Exercise the real ASRC sequence, coefficient ports and failure boundaries.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 52 | `C main` | 原检查：ASRC phase, AA, loopback restriction, timeout and every write failure passed；处置待确认 |

## `sound/soc/meson/test_t7_audio_routes.py`

类型：测试；处置待确认，保留。

原自述：Check compiled digital routes and preserve the deployed HDMI RX DT contract.  Requires cpp and dtc. --baseline is the audio-test DTB from the series base. The fixture describes hypothetical external endpoints, not VIM4 wiring. Graph reachability means a possible mux path; it cannot prove a running ALSA stream.

入口：顶层脚本；风险与分类待确认，暂保留全部断言。

## `sound/soc/meson/test_t7_audio_windows.py`

类型：测试；处置待确认，保留。

原自述：Execute MMIO callbacks against bounded banks with address sanitization.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 31 | `C main` | 待确认：核对内嵌 C 的断言 |

## `sound/soc/meson/test_t7_card.py`

类型：测试；处置待确认，保留。

原自述：Exercise real backend fixups and FE negotiation across converter stages.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 27 | `C main` | 原检查：Card unchanged legacy negotiation and 16k/6ch -> 16k/4ch + 48k/2ch fixups passed；处置待确认 |

## `sound/soc/meson/test_t7_frddr.py`

类型：测试；处置待确认，保留。

原自述：Execute playback FIFO configuration while preserving all active routes.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 44 | `C main` | 原检查：FRDDR channel count, route preservation, depth and write failures passed；处置待确认 |
