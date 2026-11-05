# 2026-11-05：内核测试清单 wave5（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/chips-media/wave5/reproduce_hang.py`

类型：板端工具；T：迁往主仓库，保留独占执行约束。

原自述：Plan, or explicitly execute, ONE exclusive Wave5 encoding/teardown trial.  Run on the board as root only inside a Mac board+heavy lock window, with video applications already stopped and a prepared recovery procedure. This program does not install, stop services, reboot, or restore a kernel. Default is plan only. --execute can wedge an affected kernel; SIGKILL cannot release a D task. Keep an independent UART log. A platform/AXI lockup can also stop this observer.

## `drivers/media/platform/chips-media/wave5/test_buffers.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise actual encoder import validation and DMA offsets without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 34 | `C main` | V/B：共享 plane 的 UV 偏移、1088 行容量和导入越界；以带流 compliance、真实 DMA-BUF 边界与 DMA 调试验证，不重造 vb2 |
| 247 | `C main` | V/B：lookahead 重排时间戳、队列公平性、LAST/drain、提交失败回滚和 destroy 失败时 DMA 留存；标准带流与实板故障注入 |
| 400 | `C main` | V/B：source index 上下界、drain sentinel 和 PTS 所有权；带流编码、调试内核越界检查 |

## `drivers/media/platform/chips-media/wave5/test_encoder_cleanup.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Inject DMA/firmware failures into the actual encoder registration and close.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 112 | `C main` | B：注册过程中逐次 DMA 分配失败、固件仍占用时 close 不能释放、重复 close 幂等；标准故障注入与真实 DMA |

## `drivers/media/platform/chips-media/wave5/test_geometry.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Check visible encoder geometry against the actual block crop calculation.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 237 | `C main` | K：非块对齐可见尺寸、AVC 偶数裁剪和 HEVC 四方向旋转后可见矩形保持；F：历史 SPS、SEI 截断/escaping 与独立 SPS 样本交标准码流分析（待实板） |

## `drivers/media/platform/chips-media/wave5/test_hang.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise selection bypasses and close/IRQ ordering using actual driver C.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 111 | `C main` | V/B：selection 不得绕过 busy/存储容量限制；两种 streamoff 顺序、并发 IRQ 与隔离 close 不能提前释放 DMA |
| 209 | `C main` | V：帧率协商、上下限和 busy sequence 拒绝；带流 compliance |

## `drivers/media/platform/chips-media/wave5/test_hang_observer.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Test observer deadlines with owned child processes; no video device access.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 18 | `test_padded_stream_does_not_pass_as_requested_geometry` | T：工具不得把填充后尺寸或少帧误判为请求尺寸/帧数；随工具迁主仓库测试 |
| 26 | `test_unkillable_child_does_not_extend_deadline` | T：不可杀子进程不能无限延长观察截止时间；随工具迁主仓库测试 |
| 34 | `test_term_then_kill_owned_process_group` | T：TERM 无效时只 KILL 自己的进程组；pipe 握手实测随工具迁移 |
