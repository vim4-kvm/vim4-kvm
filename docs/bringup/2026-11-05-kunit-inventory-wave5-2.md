# 2026-11-05：内核测试清单 wave5（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/chips-media/wave5/test_hdr10.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise real P010 setup and HDR10 serialization; parse SEI with FFmpeg.  No hardware is opened. Firmware SEI insertion and DMA sample order still need hardware acceptance before any application advertises remote HDR support.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | K：legacy P010 源字节序；V/F：P010 限 HEVC Main10、plane 容量和固件 HDR 元数据待实板；软件 SEI 构造器未接固件，原 CPU SPS/FFmpeg 结果不算硬件证据 |

## `drivers/media/platform/chips-media/wave5/test_intra_refresh.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise V4L2 refresh controls and firmware row budgets for both codecs.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | K：CTU/MB 刷新行预算含部分末行、完成周期与 codec 切换/关闭；V：period/type 控制交 compliance |

## `drivers/media/platform/chips-media/wave5/test_isolation.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Run actual quarantine/scheduler/allocator C against deterministic owners.  Models scheduler races and buffer lifetimes, not physical DMA termination.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 214 | `C main` | B/V：cancel 调度竞态、所有实例报错、迟到 IRQ、MMAP/export/import 缓冲引用、再次 timeout 和 shutdown；需实板调试内核与标准注入 |

## `drivers/media/platform/chips-media/wave5/test_profiles.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Check the actual firmware-command profile translation and control transitions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | K：legacy AVC High/High10 ABI 翻译；V：constraint 位和 codec 控制转换交带流测试 |
| 97 | `C main` | V/F：独立 LTR mark/use picture 位；带流 LTR 与输出引用检查 |
| 171 | `C main` | V/B：动态修改打包、完成所有权及 rejection/timeout 回滚；标准在线控制与故障注入 |
| 241 | `C main` | V/F：固定 QP 与 IDR 同时下发不能互相覆盖；带流输出 QP/IDR 分析 |
| 366 | `C main` | K：GOP 引用图先发布参考、层次 QP、LTR 互斥与 VBV KiB→ms 边界；V：QP/quality 控制边界、busy setters、flip、两实例隔离及在线参数交带流 |
| 651 | `C main` | V/B：custom GOP 固件 ABI、unused slot 清零及命令 timeout；带流固件与注入 |
| 721 | `C main` | V/B：延迟控制合并、失败唤醒双队列、DMA 留存和实例隔离；在线修改与真实失败 |

## `drivers/media/platform/chips-media/wave5/test_recovery.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise the production power-cycle/reload sequence with faulted PM callbacks.  The model verifies ownership and ordering, not the secure firmware or DMA bus.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 86 | `C main` | B：冷电源循环/固件重载、过期 notifier 不能授权恢复、各阶段失败须保留 PM 引用；实板标准故障注入 |

## `drivers/media/platform/chips-media/wave5/test_reset.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise actual FIO/reset C with a scripted MMIO device and virtual time.  This verifies host ordering and error propagation, not hardware DMA completion, firmware context preservation, or recovery of an M2M job.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 173 | `C main` | B：双核拒绝、FIO/idle 总截止时间、sleep/reset/wake 顺序、bus enable 失败与重复复位；必须验证实际总线 idle，不能用虚拟时间替代 |
