# 2026-11-05：内核测试清单 hdmirx（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_audio.py`

类型：测试；处置待确认，保留。

原自述：Actual audio callbacks: source races become XRUN; hardware failures unwind.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 154 | `C main` | 原检查：seven rates, packet races, native constraints, XRUN-before/after START, PLL unwind passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_buffer_layout.py`

类型：测试；处置待确认，保留。

原自述：Exercise vb2's base allocation contract through the driver's actual type.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 24 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_color.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual format reporting and protected input classification.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 55 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_copy.py`

类型：测试；处置待确认，保留。

原自述：Compare a SIMD candidate with the actual kernel memcpy_generic offline.  Linux ARM64 only. Default runs correctness checks; --output retains a standalone binary. Its --benchmark /dev/videoN mode allocates idle VDIN MMAP buffers but never starts capture. No application may own the capture queue during this run.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 47 | `C main` | 原检查：VDIN SIMD candidate: bounds, tails and scalar fallback checks passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_core.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual core lifecycle and stable-timing validation with fake registers.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 135 | `C main` | 原检查：Core lifecycle, stable start qualification and nonblocking status loss/recovery passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_ddc.py`

类型：测试；处置待确认，保留。

原自述：Compile the actual EDID/DDC functions with bounded fake MMIO and failures.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 81 | `C main` | 原检查：EDID validation, HPD ordering, bank isolation and readback failure passed；处置待确认 |
