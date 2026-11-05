# 2026-11-05：内核测试清单 hdmirx（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_audio.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Actual audio callbacks: source races become XRUN; hardware failures unwind.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 154 | `C main` | K：ACR N/CTS 计算、七种采样率和 PCM/立体声准入；V/B：音频包撕裂、source race、XRUN、PLL 超时、prepare/free 并发、时钟和寄存器恢复，ALSA 实流及标准故障注入 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_buffer_layout.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Exercise vb2's base allocation contract through the driver's actual type.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 24 | `C main` | V：vb2 首成员分配契约；保留生产 static_assert，删除重复的宿主结构体/故意改坏源码测试，真实队列分配/streaming 交 compliance 与 KASAN |

## `drivers/media/platform/amlogic/t7-hdmirx/test_color.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Exercise actual format reporting and protected input classification.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 55 | `C main` | V/F：NV12 709/limited 与 RGB sRGB/full 报告、HDR lease 身份；标准格式协商和受控颜色样本，禁止缓存 lease 混用当前输入 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_copy.py`

类型：板端工具/离线基准；T：迁出，见下表。

原自述：Compare a SIMD candidate with the actual kernel memcpy_generic offline.  Linux ARM64 only. Default runs correctness checks; --output retains a standalone binary. Its --benchmark /dev/videoN mode allocates idle VDIN MMAP buffers but never starts capture. No application may own the capture queue during this run.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 47 | `C main` | T：独立 SIMD 候选/内核 memcpy_generic 的长度尾部、保护页及 fallback；迁主仓库工具并显式提供 kernel-source；实际 MMAP benchmark 待实板 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_core.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Exercise actual core lifecycle and stable-timing validation with fake registers.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 135 | `C main` | V/B：core 开停/幂等、稳定时序准入、非阻塞状态查询、源丢失/恢复、HDR/420/444 lease 改变、包过期与撕裂、VRR 基线和测量重试；compliance/动态标准输入与实板 MMIO |

## `drivers/media/platform/amlogic/t7-hdmirx/test_ddc.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Compile the actual EDID/DDC functions with bounded fake MMIO and failures.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 81 | `C main` | K：EDID header、扩展块数、每块 checksum 和长度边界；V/B：HPD 只能在整 bank 写入且回读验证后发布、端口/复位保存恢复、写失败清理；DDC 标准接口与实板 |
