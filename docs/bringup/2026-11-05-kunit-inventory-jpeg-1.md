# 2026-11-05：内核测试清单 jpeg（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-jpeg/test_import.py`

类型：测试；处置待确认，保留。

原自述：Compile actual DMA import/release paths with tracked reservations and ownership.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | 原检查：PASS: reservation API, producer fence, partial failures, contiguous/4GiB bounds, 1000 import/release cycles；处置待确认 |

## `drivers/media/platform/amlogic/t7-jpeg/test_jpeg.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual JPEG programming, scan headers and DMA boundaries offline.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 80 | `C main` | 原检查：PASS: 100 qualities, JPEG headers, command bounds, busy/unpowered, DMA extent/4GiB / PASS: first DMA handoff, changing output lengths and imported/system-memory ownership；处置待确认 |
