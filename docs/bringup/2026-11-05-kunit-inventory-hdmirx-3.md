# 2026-11-05：内核测试清单 hdmirx（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_hlg.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Host checks for the real HLG writer, source tables and lease transitions.  Optional argument: fixed vendor set_hdr2_v0.c at common_drivers commit 8648a716befda5ec2837a7764cd61b8493db8d99. No floating-point regeneration is used: preserve the vendor's encoded EOTF, integer gain and OETF quantization.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 49 | `C main` | K：EOTF 支持及 HDR 编码切换 lease 判定；F/B：LUT 固定数据、端口打包/寄存器次序、HLG/Ys 与 gamut，标准 HLG 样本和板端写入观测 |
| 122 | `C main` | B/F：HDR 模式切换时丢首帧、跨帧 IRQ、busy 状态不得交付；真实输入切换及 DMA 调试 |
| 168 | `C main` | V/B：DRM/AVI 校验、过期/撕裂/元数据类型、动态模式开关与电源丢失；真实标准信息包和源切换 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_ioctl_locks.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Exercise actual driver registration/handlers with the core's lock selection.  Gates hold a queue operation or an RX read until the main thread releases it; timeouts only bound a failed test, never schedule the expected interleaving. Requires Linux UAPI headers, a C compiler and pthreads; no board or privileges.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 202 | `C main` | V/B：STREAMOFF 不阻塞状态查询、S_FMT 与队列互斥、旧 fd/remove 生命周期、格式容量变更和失败不提交半配置；标准 ioctl 并发与 KASAN/lockdep/注入 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_link.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Actual receiver recovery/lease code with deterministic source and PLL gates.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 159 | `C main` | B/V：无源/延迟源、独立 lease、PLL 失败、末次对齐后源丢失与恢复；实板输入切换及真实资源生命周期 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_phy.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Exercise actual PHY functions with bounded MMIO, clock loss and PLL timeout.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 118 | `C main` | B：TMDS/SCDC 时钟准入、trim、PLL 截止时间、时钟消失及错误清理；真实 PHY/时钟失败，不用寄存器和虚拟时间替代 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_source_events.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Run the actual source monitor across mode/loss/recovery transitions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 64 | `C main` | V/B：真实模式/失锁/恢复才发 source change，稳定输入不重复、撕裂计数器须重试；标准事件接口和动态输入 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_stream.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Run actual IRQ/ring/vb2 C code with deterministic hardware and CPU-copy gates.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 268 | `C main` | K：oldest-ready 槽序号与 u32 回绕；V/B/F：direct/copy 环租约、饥饿恢复、export 引用、停流和在途 CPU copy/IRQ、busy/丢 IRQ 隔离、buffer 尾容量和真实 plane 生命周期；实板标准流/调试内核 |
