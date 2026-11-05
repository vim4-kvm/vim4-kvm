# 2026-11-05：内核测试清单 drm（2）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_t7_layers.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute OSD transactions and compare scaler programming with vendor C.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 112 | `C main` | K：三层有界 RDMA 构造、地址更新快路径与完整事务回退、容量不足；F/B：scaler 系数/寄存器编程与 vendor 对照、资源 bank/VDIN arbiter 隔离，交标准图样与真实显示 |

## `drivers/gpu/drm/meson/test_t7_link_clock.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Run T7 link clock arithmetic against the vendor's 24/30-bit CTA tables.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 33 | `C main` | K：24/30-bit、420、分数时钟的 VCO/OD/TMDS 单位与范围；B：PLL 真实锁定和实际链路时钟另验 |

## `drivers/gpu/drm/meson/test_t7_modeset.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Compare executable PLL/VENC code with a local vendor source checkout.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 200 | `C main` | K：clock/mode 准入与边界；B/F：PLL/VENC/PHY、CSC、firmware 参数与 vendor 寄存器次序、独占资源/分屏范围；标准 modeset 和样本，不抽取 vendor 片段当实板 |
| 416 | `C main` | V/B：sink mode limits、SCDC 失败与 1:40/1:10、CRTC 失败和 PHY drive；真实 DRM connector/EDID |

## `drivers/gpu/drm/meson/test_t7_osd.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute OSD alpha/reflection against the vendor MIF register functions.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 56 | `C main` | K：OSD alpha unity 编码、reflection 的双向切换和无关位保留；F：实际 blending/reflect 标准图样 |

## `drivers/gpu/drm/meson/test_t7_producer_layouts.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Feed actual VDIN/Wave5 producer DMA layouts into T7 framebuffer bounds checks.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 90 | `C main` | K：framebuffer plane 完整行、UV offset 与 DMA32 边界；B/F：VDIN/Wave5 真实生产者布局、direct/copy generation/ticket、实际地址移交和采集/显示共存 |

## `drivers/gpu/drm/meson/test_t7_scanout.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise the real multi-layer DMA reference owner without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 32 | `C main` | V/B：真实 framebuffer/DMA reader 引用、相同/共享 FB、RMFB、两代 drain、迟到 completion、双阶段 transaction 与 timeout pin；标准 atomic/fence/多 plane 与 DMA 调试，不造引用计数对象 |
