# 2026-11-05：内核测试清单 drm（3）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_t7_sram.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Verify drained OSD SRAM takeover, failure unwind and the vendor firmware ABI.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | B：boot fetch 关闭并过两帧后才操作 SRAM、vsync wrap/缺失、domain attach/resume 逐次失败回收与 OSD 状态恢复；真实 genpd/IRQ |
| 173 | `C main` | B：secure firmware SRAM 电源域 ABI；真实 SMC 与域状态，不拼 vendor SMC 函数 |

## `drivers/gpu/drm/meson/test_t7_video.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute progressive T7 video MIF parameters against vendor C fragments.  No MMIO, fetch enable, scaler, blend or buffer retirement is exercised here.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 148 | `C main` | K：NV12/NV21 MIF 地址/stride/crop/vskip 与错误时不发布半状态；B/F：实际寄存器 masks/通道字节顺序和 vendor 对照交标准图样 |

## `drivers/gpu/drm/meson/test_t7_video_kms.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute video atomic validation and DMA transactions with real GEM layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 111 | `C main` | V/B/F：video plane 准入、vskip/PPS 限制、atomic 状态收集、RMFB、VD1/2 zpos、地址快路径、真实资源 bank/VDIN 隔离、DMA 前后状态；标准 DRM planes 与流/像素 |

## `drivers/gpu/drm/meson/test_t7_video_phase.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compare progressive PPS phase math with the vendor frame-to-video function.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 45 | `C main` | K：progressive PPS phase、unity 两侧/4:1 边界和拒绝时不发布半状态；F：标准缩放图样 |

## `drivers/gpu/drm/meson/test_t7_video_pps.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute PPS transactions using vendor register tables, regions and filters.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 67 | `C main` | K：PPS 描述符容量、两组相位步进、invalid 输出不写表；F/B：系数与完整 register image 对 vendor、实际 gate/缩放输出 |

## `drivers/gpu/drm/meson/test_t7_video_sync.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute scanout reader preparation, cancellation and state lifetime failures.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 100 | `C main` | V/B：生产者 fence 等待/别名、取消、两 plane 中途失败、reader/atomic state 生命周期；真实 dma_resv/fence/DRM，不重造 framework |
