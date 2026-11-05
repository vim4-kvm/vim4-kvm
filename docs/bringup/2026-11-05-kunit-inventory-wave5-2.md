# 2026-11-05：内核测试清单 wave5（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/chips-media/wave5/test_hdr10.py`

类型：测试；处置待确认，保留。

原自述：Exercise real P010 setup and HDR10 serialization; parse SEI with FFmpeg.  No hardware is opened. Firmware SEI insertion and DMA sample order still need hardware acceptance before any application advertises remote HDR support.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | 待确认：核对内嵌 C 的断言 |

## `drivers/media/platform/chips-media/wave5/test_intra_refresh.py`

类型：测试；处置待确认，保留。

原自述：Exercise V4L2 refresh controls and firmware row budgets for both codecs.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | 原检查：Wave5 cyclic row refresh, codec transitions and partial rows passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_isolation.py`

类型：测试；处置待确认，保留。

原自述：Run actual quarantine/scheduler/allocator C against deterministic owners.  Models scheduler races and buffer lifetimes, not physical DMA termination.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 214 | `C main` | 原检查：Wave5 isolation/recovery: cancel races, all-instance errors, late IRQ, MMAP/export/import retention and reclamation, repeat timeout and shutdown passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_profiles.py`

类型：测试；处置待确认，保留。

原自述：Check the actual firmware-command profile translation and control transitions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | 原检查：Wave5 legacy AVC profiles and constraint transitions passed；处置待确认 |
| 97 | `C main` | 原检查：Wave5 independent LTR mark/use picture bits passed；处置待确认 |
| 171 | `C main` | 原检查：Wave5 dynamic packing, completion ownership and rejection/timeout rollback passed；处置待确认 |
| 241 | `C main` | 原检查：Wave5 fixed QP and simultaneous IDR command packing passed (208 cases)；处置待确认 |
| 366 | `C main` | 原检查：Wave5 28 multi-B/hierarchical GOP graphs, boundaries and LTR combinations passed / Wave5 codec control isolation, busy setters, flip reversal and two instances passed；处置待确认 |
| 651 | `C main` | 原检查：Wave5 custom GOP firmware ABI, unused slots and timeout boundary passed；处置待确认 |
| 721 | `C main` | 原检查：Wave5 deferred changes: coalescing, queue wakeup, DMA retention and instance isolation passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_recovery.py`

类型：测试；处置待确认，保留。

原自述：Exercise the production power-cycle/reload sequence with faulted PM callbacks.  The model verifies ownership and ordering, not the secure firmware or DMA bus.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 86 | `C main` | 原检查：Wave5 recovery: cold reload, 8 failure boundaries and 5 one-shot injections passed；处置待确认 |

## `drivers/media/platform/chips-media/wave5/test_reset.py`

类型：测试；处置待确认，保留。

原自述：Exercise actual FIO/reset C with a scripted MMIO device and virtual time.  This verifies host ordering and error propagation, not hardware DMA completion, firmware context preservation, or recovery of an M2M job.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 173 | `C main` | 待确认：核对内嵌 C 的断言 |
