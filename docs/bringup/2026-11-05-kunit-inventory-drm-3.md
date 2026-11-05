# 2026-11-05：内核测试清单 drm（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_t7_sram.py`

类型：测试；处置待确认，保留。

原自述：Verify drained OSD SRAM takeover, failure unwind and the vendor firmware ABI.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | 待确认：核对内嵌 C 的断言 |
| 173 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_video.py`

类型：测试；处置待确认，保留。

原自述：Execute progressive T7 video MIF parameters against vendor C fragments.  No MMIO, fetch enable, scaler, blend or buffer retirement is exercised here.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 148 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_video_kms.py`

类型：测试；处置待确认，保留。

原自述：Execute video atomic validation and DMA transactions with real GEM layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 111 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_video_phase.py`

类型：测试；处置待确认，保留。

原自述：Compare progressive PPS phase math with the vendor frame-to-video function.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 45 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_video_pps.py`

类型：测试；处置待确认，保留。

原自述：Execute PPS transactions using vendor register tables, regions and filters.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 67 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/gpu/drm/meson/test_t7_video_sync.py`

类型：测试；处置待确认，保留。

原自述：Execute scanout reader preparation, cancellation and state lifetime failures.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | 原检查：Video readers: producer ordering, aliases, cancellation, split failure and state lifetime passed；处置待确认 |
