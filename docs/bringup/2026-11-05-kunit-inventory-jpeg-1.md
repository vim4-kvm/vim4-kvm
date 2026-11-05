# 2026-11-05：内核测试清单 jpeg（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-jpeg/test_import.py`

类型：测试；B：真实 DMA-BUF 导入与故障注入，待实板。

原自述：Compile actual DMA import/release paths with tracked reservations and ownership.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 79 | `C main` | B：producer fence 等待、reservation 锁 API、attach/map 的逐次失败回收、连续 SG 与 4GiB 边界、重复导入/释放、运行中 busy；真实 DMA-BUF/调试内核标准注入，不重造 allocator/reservation 框架 |

## `drivers/media/platform/amlogic/t7-jpeg/test_jpeg.py`

类型：测试；K：量化表及 JPEG 头；B/F：硬件编程、DMA 与标准样本，待实板。

原自述：Exercise actual JPEG programming, scan headers and DMA boundaries offline.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 80 | `C main` | K：百档质量的量化边界/单调性、JPEG DQT/DHT/SOF/SOS 序列化及扫描起点对齐；B：命令格式与存储范围拒绝、未供电/busy 不写寄存器、输入地址/UV 偏移/4GiB、首次及长短输出切换的 DMA 同步、导入与系统内存所有权；F：标准样本完整解码与像素比对 |

顶层 Pillow 中性 16×16 像素检查是 F：宿主拼接软件扫描段不能证明真实编码输出，
交标准输入样本的硬件输出解码/像素比对，待实板。现有 jpegenc 兼容 ABI 本轮不改，
也不以它冒充 V4L2 compliance；其 DMA/命令边界由板端接口工具与调试配置验证。
