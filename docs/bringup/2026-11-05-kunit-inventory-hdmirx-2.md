# 2026-11-05：内核测试清单 hdmirx（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_edid_runtime.py`

类型：测试；处置待确认，保留。

原自述：Run actual EDID operations across leases, partial reads and failed writes.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_export_identity.py`

类型：测试；处置待确认，保留。

原自述：Run vb2's actual export callback twice against one allocator.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr10_native.py`

类型：测试；处置待确认，保留。

原自述：Run actual AMLY reporting, byte budget and HDMI metadata getters off-board.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 68 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_crc.py`

类型：测试；处置待确认，保留。

原自述：Check actual LUT CRC code against independent canonical zlib vectors.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_curve.py`

类型：测试；处置待确认，保留。

原自述：Compile the real curve parser against malformed and boundary transactions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 34 | `C main` | 原检查：HDR curve transactions: valid pair, truncation, excess, range and endpoint guards passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_resources.py`

类型：测试；处置待确认，保留。

原自述：Execute actual PQ writer and pool limits without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 36 | `C main` | 待确认：核对内嵌 C 的断言 |
