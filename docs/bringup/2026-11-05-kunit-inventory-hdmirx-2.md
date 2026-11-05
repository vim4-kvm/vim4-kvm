# 2026-11-05：内核测试清单 hdmirx（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/media/platform/amlogic/t7-hdmirx/test_edid_runtime.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Run actual EDID operations across leases, partial reads and failed writes.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 46 | `C main` | V/B：相同 EDID 幂等、lease/busy 拒绝更新、分块读取、写失败恢复旧内容、禁用 EDID 与 core/DDC 所有权；标准 EDID 接口和注入 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_export_identity.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Run vb2's actual export callback twice against one allocator.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | V/B：两次 export 不同 DMA-BUF/inode 仍共享同一 allocator；按实际 DMA-BUF 存储身份判断与引用计数生命周期，不重建 vb2 allocator |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr10_native.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Run actual AMLY reporting, byte budget and HDMI metadata getters off-board.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 68 | `C main` | V/F/B：AMLY/YUV24 格式与对齐、真实字节预算、REQBUFS/CREATE_BUFS 上限、HDR10 元数据单位/缺失/过期、native 色域/深度/范围准入；标准接口及样本捕获，分配失败另验 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_crc.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Check actual LUT CRC code against independent canonical zlib vectors.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | K：LUT 端口样本 little-endian CRC、右移量、空输入；用独立 zlib 向量验证生产 CRC |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_curve.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Compile the real curve parser against malformed and boundary transactions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 34 | `C main` | K：完整双曲线事务、每个截断边界、过量/非数字/负值、12 位范围、gain 递减/OETF 递增及端点约束 |

## `drivers/media/platform/amlogic/t7-hdmirx/test_hdr_resources.py`

类型：测试；处置见下表，V/B/F 均待实板。

原自述：Execute actual PQ writer and pool limits without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 36 | `C main` | V/B/F：REQBUFS/CREATE_BUFS/faulted 队列预算、PQ 写入、精确 gamut 系数和源隔离；真实队列/分配与标准像素样本；不保留寄存器数组 mock |
