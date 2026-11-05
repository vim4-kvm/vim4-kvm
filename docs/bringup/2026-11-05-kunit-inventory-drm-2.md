# 2026-11-05：内核测试清单 drm（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_t7_layers.py`

类型：测试；处置待确认，保留。

原自述：Execute OSD transactions and compare scaler programming with vendor C.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 112 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_link_clock.py`

类型：测试；处置待确认，保留。

原自述：Run T7 link clock arithmetic against the vendor's 24/30-bit CTA tables.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_modeset.py`

类型：测试；处置待确认，保留。

原自述：Compare executable PLL/VENC code with a local vendor source checkout.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 200 | `C main` | 待确认：核对内嵌 C 的断言 |
| 416 | `C main` | 原检查：Bridge: sink mode limits, SCDC failure/1:40/1:10, failed CRTC and vendor PHY drives passed；处置待确认 |

## `drivers/gpu/drm/meson/test_t7_osd.py`

类型：测试；处置待确认，保留。

原自述：Execute OSD alpha/reflection against the vendor MIF register functions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 56 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_producer_layouts.py`

类型：测试；处置待确认，保留。

原自述：Feed actual VDIN/Wave5 producer DMA layouts into T7 framebuffer bounds checks.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 90 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_scanout.py`

类型：测试；处置待确认，保留。

原自述：Exercise the real multi-layer DMA reference owner without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | 待确认：核对内嵌 C 的断言 |
