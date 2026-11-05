# 2026-11-05：内核测试清单 drm（1）

基线 `2662456a1a636f668454ab04a1c63f567206a592`。
逐文件保留原入口和原测试自述（英文）；内嵌 C 的 `main` 按字符串起始行定位。
“待确认”表示尚未逐条核对断言，保留原文件，不授权删除；自述不能替代风险审查。
K＝生产纯函数 KUnit；V＝标准接口/带流；B＝实板电源、时钟、DMA/故障；
F＝标准样本数据比对；T＝工具迁出。V/B/F 均待实板。

## `drivers/gpu/drm/meson/test_hdmitx21.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Run the TX transport and DDC state machine with deterministic firmware replies.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 37 | `C main` | B：SMC TOP32/COR8 transport 的参数与错误传播；真实 firmware 调用与寄存器访问 |
| 108 | `C main` | V/B：初次无 HPD、bounce、插拔、读取失败及同步取消监测；DRM connector/HPD 与实板源切换 |
| 198 | `C main` | V/B：多块 EDID、NACK/busy、空 FIFO 截止时间、overrun 与非法 I2C 消息；标准 DDC/EDID 及调试配置 |
| 266 | `C main` | V/B：inactive/DVI 拒绝 PCM、rate/width/channel 准入、mute/shutdown；标准 ALSA/HDMI 端口实流 |
| 372 | `C main` | B：ACR clock、DVI gating、mute 持久性和 packet bank 锁；实板音视频与锁调试 |
| 427 | `C main` | K：固定 firmware 模式的宽高/clock/porch/flags 准入；B：DTB 的 HDMI audio 路由另验 |

## `drivers/gpu/drm/meson/test_hdmitx21_color.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise actual TX CSC writes, AVI range and EDID format admission together.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 59 | `C main` | V/B/F：EDID sink 色彩组合、CSC/AVI range 与 720p/1080p/4K 保持一致；标准 DRM atomic/EDID 和像素样本 |

## `drivers/gpu/drm/meson/test_t7_boot.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Reject foreign AFBC and incompatible boot fetches before RDMA takeover.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 50 | `C main` | B：foreign AFBC/不兼容 fetch 不得被接管、native fallback 与 boot takeover guard；真实 firmware 画面和接管；源码调用先后检查不能证明硬件安全 |

## `drivers/gpu/drm/meson/test_t7_fb.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Exercise complete-row bounds for linear RGB and producer NV12 layouts.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 38 | `C main` | K：真实 DRM framebuffer/GEM DMA 类型的末行 padding、plane offset、独立 NV12 import、stride/modifier、DMA32 及容量边界；B：实际导入另验 |

## `drivers/gpu/drm/meson/test_t7_handoff.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute the handoff IRQ and buffer retirement with controlled vsync delivery.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 388 | `C main` | V/B：双 vsync 回收、active RMFB、wrap、timeout pin、RDMA IRQ 两种顺序、latch 失败 event/fence、native modeset/drain/PLL 失败、排队 commit 身份、三 OSD 和 video 两阶段引用、连续地址更新；IGT/modetest、真实 DMA/IRQ/显示共存，不重建 DRM 调度 |

## `drivers/gpu/drm/meson/test_t7_hdmi_atomic.py`

类型：测试；处置见下表，V/B/F 全部待实板。

原自述：Execute HDMI atomic admission and packet bank ownership without hardware.

| 基线行 | 测试入口 | 原风险/处置 |
|---|---|---|
| 120 | `C main` | V/B/F：HDR EOTF/depth/range、混合 gamut 拒绝、420/SCDC、affected planes/RMFB、packet bank 清除；标准 DRM atomic/EDID/色彩样本 |
