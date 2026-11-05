# 2026-11-05：内核测试清单 hdmirx（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py`

类型：测试；处置待确认，保留。

原自述：Host checks for the real HLG writer, source tables and lease transitions.  Optional argument: fixed vendor set_hdr2_v0.c at common_drivers commit 8648a716befda5ec2837a7764cd61b8493db8d99. No floating-point regeneration is used: preserve the vendor's encoded EOTF, integer gain and OETF quantization.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 49 | `C main` | 待确认：核对内嵌 C 的断言 |
| 122 | `C main` | 待确认：核对内嵌 C 的断言 |
| 168 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_ioctl_locks.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual driver registration/handlers with the core's lock selection.  Gates hold a queue operation or an RX read until the main thread releases it; timeouts only bound a failed test, never schedule the expected interleaving. Requires Linux UAPI headers, a C compiler and pthreads; no board or privileges.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 202 | `C main` | 原检查：ioctl locks: status during gated stop, S_FMT exclusion, query/removal and old fd passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_link.py`

类型：测试；处置待确认，保留。

原自述：Actual receiver recovery/lease code with deterministic source and PLL gates.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 159 | `C main` | 原检查：Receiver recovery: absent/delayed source, DMA leases, PLL failure and late alignment passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_phy.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual PHY functions with bounded MMIO, clock loss and PLL timeout.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 118 | `C main` | 原检查：PHY clock/SCDC qualification, trim, bounded PLL timeout and cleanup passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_source_events.py`

类型：测试；处置待确认，保留。

原自述：Run the actual source monitor across mode/loss/recovery transitions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 64 | `C main` | 原检查：Source monitor: real mode/loss/recovery events, stable input and torn-counter retry passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_stream.py`

类型：测试；处置待确认，保留。

原自述：Run actual IRQ/ring/vb2 C code with deterministic hardware and CPU-copy gates.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 268 | `C main` | 原检查：DMA ring/direct leases: ownership, starvation, in-flight stop, busy IRQ and quarantine passed；处置待确认 |
