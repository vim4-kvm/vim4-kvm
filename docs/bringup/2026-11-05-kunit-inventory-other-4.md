# 2026-11-05：内核测试清单 other（4）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/usb/typec/tcpm/test_fusb302_sink.py`

类型：测试；处置待确认，保留。

原自述：Run the production regulator paths with fake supplies, without PD I/O.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 58 | `C main` | 待确认：核对内嵌 C 的断言 |
