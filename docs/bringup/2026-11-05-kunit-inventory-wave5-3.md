# 2026-11-05：内核测试清单 wave5（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/chips-media/wave5/test_vui.py`

类型：测试；K：VUI 序列化迁 KUnit；F：完整 SPS 语法和固件码流待实板。

原自述：Parse real AVC/HEVC SPS fixtures containing the actual driver's VUI bytes.  Fixtures are CPU-encoded 64x64 red frames, with encoder SEI removed. This proves serialization, not that T7 firmware accepts the RBSP command.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 47 | `C main` | K：默认色彩参数、AVC/HEVC 位长、非法 transfer/matrix/quantization；防错误 VUI 被固件接受 |

顶层 `trace`/SPS 替换循环：K 检查 709、sRGB、PQ/full 的序列化字段；
F 交给标准样本和实际固件输出的语法验证，待实板。原 FFmpeg 拼接 CPU SPS
只能证明软件序列化，不能证明固件接受 VUI。
