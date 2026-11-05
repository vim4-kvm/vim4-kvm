# 2026-11-05：内核测试清单 audio（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `sound/soc/meson/test_t7_aed.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute the real AED SRAM, biquad validation and enable/failure sequence.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | K：Q23 biquad 稳定性、系数位宽及 full/multiband DRC 约束；B/F：双 SRAM、FIFO source 隔离、enable 次序与每个 regmap 失败，ALSA 样本及标准注入 |

## `sound/soc/meson/test_t7_asrc.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise the real ASRC sequence, coefficient ports and failure boundaries.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 52 | `C main` | V/B/F：采样率/通道/loopback 准入、phase/AA/SINC 表、转换使能与 timeout/逐写失败；标准 ALSA 变率样本、寄存器和调试内核 |

## `sound/soc/meson/test_t7_audio_routes.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Check compiled digital routes and preserve the deployed HDMI RX DT contract.  Requires cpp and dtc. --baseline is the audio-test DTB from the series base. The fixture describes hypothetical external endpoints, not VIM4 wiring. Graph reachability means a possible mux path; it cannot prove a running ALSA stream.

入口：顶层脚本；V/B：DAPM 图可达性、FIFO/ASRC/loopback 通路、CPU DAI 去重、保留 HDMI RX DT 合同及 MMIO window 不重叠。实际路由交 ALSA/DAPM 与标准 DT schema/DTB 检查；脚本自述的假想外部端点不是 VIM4 接线，不保留自造场景作为通过证据。

## `sound/soc/meson/test_t7_audio_windows.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute MMIO callbacks against bounded banks with address sanitization.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 31 | `C main` | B：分 bank MMIO callbacks 不越界或访问相邻 core；真实资源映射与调试内核，不构造寄存器数组 |

## `sound/soc/meson/test_t7_card.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise real backend fixups and FE negotiation across converter stages.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 27 | `C main` | K：真实 ASoC 参数对象的 BE rate/channels fixup、无转换时保留参数、转换两侧 FE merged 标志；V：实际路由协商与多级转换实流 |

## `sound/soc/meson/test_t7_frddr.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute playback FIFO configuration while preserving all active routes.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 44 | `C main` | V/B：播放 FIFO 通道/depth 准入、活动路由位保留、读写失败不得继续编程；标准 PCM 与故障注入 |
