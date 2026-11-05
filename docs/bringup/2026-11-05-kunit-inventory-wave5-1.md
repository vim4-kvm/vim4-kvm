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

类型：测试；处置待确认，保留。

原自述：Exercise actual encoder import validation and DMA offsets without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 34 | `C main` | 原检查：Wave5 shared DMA plane offsets and bounds passed；处置待确认 |
| 247 | `C main` | 原检查：Wave5 lookahead ownership, reordered timestamps, fair scheduling and drain passed；处置待确认 |
| 400 | `C main` | 原检查：Wave5 source index boundaries, drain and timestamp ownership passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_encoder_cleanup.py`

类型：测试；处置待确认，保留。

原自述：Inject DMA/firmware failures into the actual encoder registration and close.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 112 | `C main` | 原检查：Wave5 allocation rollback, firmware ownership and close passed (32 cases)；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_geometry.py`

类型：测试；处置待确认，保留。

原自述：Check visible encoder geometry against the actual block crop calculation.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 237 | `C main` | 原检查：Wave5 AVC visible geometry, even crop units and rotated padding passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_hang.py`

类型：测试；处置待确认，保留。

原自述：Exercise selection bypasses and close/IRQ ordering using actual driver C.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 111 | `C main` | 原检查：Wave5 selection/firmware geometry (20 cases) and close/IRQ ordering (8 cases) passed；处置待确认 |
| 209 | `C main` | 原检查：Wave5 negotiated frame intervals and busy sequence state passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_hang_observer.py`

类型：测试；处置待确认，保留。

原自述：Test observer deadlines with owned child processes; no video device access.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 18 | `test_padded_stream_does_not_pass_as_requested_geometry` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 26 | `test_unkillable_child_does_not_extend_deadline` | 待确认：逐条核对 Python 断言后决定替代路径 |
| 34 | `test_term_then_kill_owned_process_group` | 待确认：逐条核对 Python 断言后决定替代路径 |
