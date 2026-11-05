# 2026-11-05：内核测试清单 other（4）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/usb/typec/tcpm/test_fusb302_sink.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Run the production regulator paths with fake supplies, without PD I/O.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 58 | `C main` | V/B：sink-only 无 vbus regulator、defer/其他错误不能当 absent、source/dual 必须有供电、charge 标志及 enable/disable 幂等；标准 TCPM/PD 及真实 regulator，PWM provider 本轮不改 |
