# 2026-11-05：内核测试清单 drm（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_hdmitx21.py`

类型：测试；处置待确认，保留。

原自述：Run the TX transport and DDC state machine with deterministic firmware replies.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 37 | `C main` | 原检查：TX firmware transport: TOP32/COR8 read and write arguments passed；处置待确认 |
| 108 | `C main` | 原检查：HPD: cold unplug, bounce, plug, read error, unplug and synchronous stop passed；处置待确认 |
| 198 | `C main` | 原检查：DDC: 8 EDID blocks, NACK, busy, empty FIFO timeout, FIFO overrun and malformed transfers passed；处置待确认 |
| 266 | `C main` | 原检查：HDMI codec: inactive/DVI refusal, PCM rate/width/channel bounds and mute/shutdown passed；处置待确认 |
| 372 | `C main` | 原检查：Audio registers: ACR clocks, DVI gating, persistent mute and packet-window locking passed；处置待确认 |
| 427 | `C main` | 原检查：Firmware mode gate: 4K/720p, alternate clock/porches, interlace and doublescan rejected；处置待确认 |

## `drivers/gpu/drm/meson/test_hdmitx21_color.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual TX CSC writes, AVI range and EDID format admission together.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 59 | `C main` | 原检查：TX colour: 32 sink combinations; 720p/1080p/4K CSC and BT.709 limited AVI agree；处置待确认 |

## `drivers/gpu/drm/meson/test_t7_boot.py`

类型：测试；处置待确认，保留。

原自述：Reject foreign AFBC and incompatible boot fetches before RDMA takeover.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | 原检查：Boot takeover: native 720p fallback and unchanged fetch/AFBC/legacy guards passed；处置待确认 |

## `drivers/gpu/drm/meson/test_t7_fb.py`

类型：测试；处置待确认，保留。

原自述：Exercise complete-row bounds for linear RGB and producer NV12 layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 38 | `C main` | 原检查：Linear MIF: final-row padding, independent NV12 imports, offsets and DMA32 bounds passed；处置待确认 |

## `drivers/gpu/drm/meson/test_t7_handoff.py`

类型：测试；处置待确认，保留。

原自述：Execute the handoff IRQ and buffer retirement with controlled vsync delivery.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 388 | `C main` | 原检查：OSD two-vsync retirement, active-CRTC RMFB, wrap and timeout pinning passed / Linear OSD: RGB32 layout, padding/modifier rejection, vsync programming and boot restore passed / RDMA: 60 flips/60 vsyncs, IRQ orders/wrap, detach, missing DMA/vsync pinning passed / Latch failure: no successful page-flip event, error fence and released commit dependency passed / Native atomic modeset: deferred initial flip, 4K geometry, blank/drain/stop and PLL failure passed / Queued atomic states: scanout and event belong to the submitted commit, not global state / Three OSD engines: 60 safe events/60 vsyncs, long-update event delay, RMFB and drain fault pinning passed / Video retirement: two-phase latch/drain, two video references, RMFB and enable failure pinning passed / VD1 address updates: 120 generations, one latch per vsync and unchanged full-scan retirement passed；处置待确认 |

## `drivers/gpu/drm/meson/test_t7_hdmi_atomic.py`

类型：测试；处置待确认，保留。

原自述：Execute HDMI atomic admission and packet bank ownership without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 120 | `C main` | 原检查：HDMI atomic: HDR/EOTF/depth/range, mixed-gamut refusal, 420/SCDC, RMFB and packet clearing passed；处置待确认 |
