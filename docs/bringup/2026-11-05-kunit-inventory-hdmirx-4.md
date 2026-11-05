# 2026-11-05：内核测试清单 hdmirx（4）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_timings.py`

类型：测试；处置待确认，保留。

原自述：Run the actual RX timing query and VDIN ioctls against register transitions.  Requires Linux UAPI headers, but no board, kernel modules or privileges.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 106 | `C main` | 原检查：RGB/444/422/420, 8/10/12-bit, range/601/709 and unsupported HDR guards passed / Measured timing ioctls: UHD/FHD, fractional rate, torn counter, loss, unsupported modes passed；处置待确认 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_vdin.py`

类型：测试；处置待确认，保留。

原自述：Run actual snapshot IRQ/capture code against bounded MMIO and failure schedules.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 150 | `C main` | 原检查：VDIN completion ordering, DMA bounds, timing change and timeout containment passed；处置待确认 |
