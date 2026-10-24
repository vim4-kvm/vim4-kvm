# 2026-10-23：M3 HDMI HDR、10-bit、420 与跳行缩放（离线）

接续 [VD1/VD2 与 NV12](2026-10-23-display-m3-video-planes.md)。本批接入标准
HDMI atomic state、HDR DRM infoframe、max bpc、Colorspace 和 YUV420，并补齐
4K NV12 → 1080p60 的逐行跳行读取。**仅离线实现，尚无新路径的物理输出证据。**
本轮没有访问板子、安装候选或改变正式部署；M2 物理颜色、TX 出声和拔插仍待验。

## 实现与提交

| 提交 | 内容 |
|---|---|
| `dc8a926aded95` | 按像素时钟、8/10 bpc 和 420 计算 PLL、链路分频与 TMDS |
| `d1afded9b36ee` | atomic-color binding，新增窄 formatter / OSD matrix 窗口 |
| `132831012a55c` | 标准 HDMI state、HDR/AVI packet、色彩矩阵、10-bit/420 与 ACR |
| `330acaa9965cd` | VD1/VD2 progressive vskip 与 modeset 后安全重建 MIF |

内核功能分支为 `vim4-display-m3`。新功能由 M3 / M3-video DT 的
`amlogic,atomic-color` 显式启用；M2 DT 保持原有 8-bit YUV444 输出策略。
没有修改正式 `vim4-kvm-7.3`、部署锁、U-Boot 或应用。

`drm_bridge_connector` 的 HDMI 标志启用 `drm_hdmi_state_helper`，由标准 helper
按 EDID 协商格式、位深和 TMDS，并生成 AVI/HDR/vendor infoframe。驱动使用
connector 标准 `HDR_OUTPUT_METADATA`、`max bpc`、`Colorspace`、`Broadcast RGB`
和 color format 属性；没有另建私有 HDR ABI。传输格式和位深取自本次提交的
`connector_state->hdmi`，VPP、PLL、TX、PHY、SCDC 与音频使用同一选择。

| 属性 / 传输 | 本候选行为与限制 |
|---|---|
| max bpc | 8..10；EDID 不支持的深色由 helper 拒绝或降低实际 bpc |
| RGB444 | BT.709 转 RGB full；AUTO / FULL 为 full，LIMITED 拒绝 |
| YUV444 / YUV420 | limited；AVI YCC 范围与实际矩阵一致，不支持 YUV422 |
| Colorspace | Default / BT709_YCC / BT2020_YCC；Default 也使用 BT.709 |
| BT2020_YCC | 仅 YUV 传输；不允许现有 BT.709 NV12/NV21 视频层同时启用 |
| HDR metadata | 需 HDMI sink、10 bpc、BT2020_YCC、type 0、sink EDID 对应 EOTF |
| HDR 清除 | disable 清 DRM bank；HDR→SDR / metadata 改变触发 modeset 并更新 packets |
| 420-only | 主线 helper 根据 EDID 420-only 位限制为 420，水平像素及总周期须偶数 |
| SCDC | 按实际 TMDS：超过 340MHz 需 sink SCDC + scrambling，写配置失败保持静音 |

HDR 用户态须同时设置支持的 YUV color format、BT2020_YCC 和 max bpc=10；
Colorspace 不会代替 color format 选择。当前内核 display_info 没有独立 BT.2020
colorimetry 能力字段，驱动校验 EDID HDR EOTF，用户态仍需核对 sink 的 BT.2020
色度支持。当前线性 RGB framebuffer 仍为 8-bit；10-bit 指 HDMI 传输位深，
不意味着增加源缓冲精度。没有实现 tone mapping、gamut mapping 或 P010。
源内容须已按指定色域 / EOTF 编码；不能把 SDR 像素加上 HDR metadata 当成 HDR 转换。

## 厂商对照与寄存器所有权

硬件依据固定 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`：

- `hdmitx21/hw/hw_clk.c` 的 T7 `hdmitx21_set_clk()`、24/30-bit clock tables：
  10-bit 使用 VID PLL 6.25 分频，420 改变 OD、PNX / pixel 分频；没有复制 S5/S7 分支。
- `hdmitx21/hw/hdmi_tx_hw.c:config_hdmi21_tx()`：P2T deep-color、输入 mask、
  GCP、CSC preset 0x65、T7 formatter 和 HDMI_SETTING 的 pre/post 映射。
- `hdmi_tx_pktmgmt.c`：AVI bank 0、audio bank 2、vendor bank 5、DRM bank 6；
  packet mutex 串行写 bank，清 HDR 不碰音频 bank。
- `osd_reg.h` / `osd_hw.c` 与 `amvecm/amcsc.c`：VPP0 OSD blend matrix
  0x3910..0x391d、BT.709 / BT.2020 limited 系数及各自负数舍入宏。
  没有误用 0x3d60 的 WRAP matrix。

新增窗口为 HDMI_FMT_CTRL 0xff009d0c/4 和 OSD matrix 0xff00e440/0x38；
M3 OSD profile 共 24 个 display resource，video profile 共 44 个。schema 同时保留
旧资源列表兼容。测试核对与 VDIN split MMIO 不相交；不写 VDIN arbitration、
canvas、RX PLL/reset，不调整共享 VPU 时钟。实际内存带宽共存仍需上板确认。

链路时钟由像素时钟计算，不把深色 TMDS 当作 pixel clock：

| 像素 / 格式 | 实际 TMDS | SCDC scrambling |
|---|---|---|
| 148.5MHz，444 8-bit | 148.5MHz | 关闭 |
| 148.5MHz，444 10-bit | 185.625MHz | 关闭 |
| 594MHz，420 8-bit | 297MHz | 关闭 |
| 594MHz，420 10-bit | 371.25MHz | 开启 |
| 594MHz，444 10-bit | 742.5MHz | 超过 600MHz，拒绝 |

PHY 阈值、SCDC 和 ALSA ACR 都使用实际 TMDS；ACR 保留 Hz 精度，例如
92,812,500Hz，避免先舍入到 kHz 引入音频误差。PLL 仍按已有 3..6GHz VCO、
25.175..594MHz pixel 范围计算，表外模式继续受 VENC 几何与刷新边界检查。

## 4K → 1080p60 跳行读取

厂商 `video_sink/vpp.c:vpp_process_speed_check()` 对未压缩 4K、向下缩放且输出
超过 30Hz 要求 vskip。`video_hw.c:vd1_set_dcu()` / `vdx_set_dcu()` 的逐行路径
使用 Y/UV 四个 repeat pattern=0x8、loop=0。当前仅实现 vskip=1：MIF 保持完整
DMA 范围和 stride，Y/UV 跳行，PPS / HDR input / VPP 输入高度取一半，再做剩余缩放。
crop 的 y 和高度须 4 行对齐，避免不完整的色度行对；其他 skip 因子拒绝。

保持现有 VPU 实际频率下的吞吐检查，不写共享时钟。逐行跳行会丢失垂直细节，
不是完整 2160 行滤波降采样。4K→1080p30 继续完整帧 PPS。

同时修复 modeset 后同几何可能误走地址更新的问题：modeset 已断开 MIF 时，即使
FB 尺寸不变，也必须走两阶段重建 / 接回。保留视频额外扫描周期退休与故障 pinning；
OSD 每 vblank 翻页路径不变。**视频地址更新仍保守约 30 次/秒，不声称 60 flips/s。**

## 离线验证

`test_t7_link_clock.py` 执行实际 C 计算，与厂商 24/30-bit 表的九种 profile 对照，
另扫表外时钟和拒绝边界。`test_t7_modeset.py` 比较实际 PLL/VENC 写入、两种矩阵
系数和 T7 formatter 原始表达式，覆盖 8/10-bit、420、4K 及非法深色速率。

`test_t7_hdmi_atomic.py` 执行实际 bridge atomic check 和 packet 写入函数，覆盖
RGB 范围、HDR 深度/EOTF/type、空/错长 blob、混合色域、RMFB 空 FB、420 SCDC、
奇数水平时序，以及 DRM bank 清除不影响 audio bank。该测试传入已选择的 HDMI state，
**不等同于执行完整 EDID 协商，也没有验证真实 sink 行为。**

`test_t7_video.py` 执行厂商两路 DCU 原始块与实际 MIF builder，128 组参数覆盖
Y/UV repeat、地址、formatter、stride 和拒绝边界。video KMS 测试覆盖双路跳行、
有效输入高度、完整 DMA scope、4K30/60 切换，以及 modeset 强制两阶段重建。
既有 RMFB、60/60 OSD、fence/退休、SRAM、producer 布局、CEC/RX/Wave5 回归继续运行。

完整构建、strict checkpatch、artifact 哈希与主仓测试结果将在本批验证结束后补齐。

## P010 / AFBC 继续保留的门禁

P010 仍未公开：T7 `video_hw.c` 没有明确的 bit16 / P010 unpack；已知 bit7 实现
在 `video_hw_s5.c`，不能移给 T7。需要 T7 MIF 对高 10-bit、低填充、endian、
16-bit stride 的寄存器依据，以及 VDIN/Wave5/vdec 实际 producer 布局对照。

AFBC 仍仅记录：需可验证的 configuration-swapped / surfaces-completed 代际完成，
包括陈旧 IRQ、多 surface、双 decoder core、disable 排空及故障固定引用合同。
surface enable 清零、raw error status 和普通 MIF 额外 vsync 均不能证明 decoder idle。
在这些证据补齐前不公开 Mali AFBC modifier。

## M2 + M3 一次性启动批量上板清单

先按部署文档 rebase 当时正式 HEAD，重建同次 Image/DTB/完整模块。备份及默认项
保持当时正式部署，只用已验证的一次性启动；复位 / watchdog 后回默认项。每组持
board + heavy 双锁，按短窗口释放。M3-video 首先只读核对 boot routing / fetch-off
合同，匹配后才让 probe 领取 15 个 SRAM domain；不匹配应安全拒绝。

无需用户在场、但仍须获得板子测试窗口的项目：

1. HPD 当前电平、EDID 原文与模式/420-only/deep-color/HDR 能力；只测当前 sink 声明
   支持的 720p、1080p50/60、1440p、4K30/60。读回 PLL、VENC、GCP/P2T、formatter，
   比较所选 bpc / 格式、TMDS 与 SCDC，8↔10、444↔420 往返。
2. HDR blob 更新和移除、SDR 往返、AVI / DRM bank 与标准 debugfs infoframe；
   错误 EOTF/type、错误色域混合、RGB limited、无 SCDC 的高 TMDS 应拒绝。
3. OSD 1080p60 60 flips/s、panfrost renderer 与 linear PRIME 直接 scanout；
   cursor / overlay、zpos、alpha、缩放和 RMFB/disable。不能用 llvmpipe 代替 GPU。
4. VD1/VD2 单/双对象 NV12、VDIN/Wave5/vdec stride/offset、延迟 IN_FENCE、
   同几何 modeset、4K→1080p30/60、两路混合及旧缓冲退休；producer 不得提早 QBUF。
   检查跳行图样、framebuffer 引用、超时错误 fence 与 pinning，视频速率单独统计。
5. 模式切换期间 4K60 HDMI-IN 编码和音频连续性、tmds-invalid、HID/UDC、
   oops/taint；电源所有权改动按部署门禁执行九类全量回归。

需用户在场 / 合适显示设备的项目：

1. Mac Chrome 抓帧页授权后验证 M2 SMPTE/纯色块及 GPU 颜色：各通道误差≤16/255、
   中性灰通道差≤8、黑≤8；记录采集格式、量化范围及转换，超差不验收。
2. HDMI-OUT 997Hz 测试音，经 Mac 采集卡物理录音和频谱确认，同时 HDMI-IN 音频工作；
   ALSA 写入成功不能替代出声证据。使用系统 Chrome，不用 Playwright 申请摄像头/麦克风。
3. HDMI-OUT 拔插、无显示器启动与重连，确认 EDID / ELD、声卡、画面与采集恢复。
4. 支持 1440p / 4K60 / 420 / HDR10 / 10-bit 的 sink 上验证对应模式、HDR 状态及渐变；
   普通采集卡不支持的能力不能据其画面宣称通过，必要时用接收端状态或分析仪读 packets。

每组结束重启回默认正式基线，确认实际 build ID、KVM/manager/隔离监控 active、
isolated=0、taint=0、画面、一路编码、UDC configured 和 HID，再清理本窗口临时文件、
释放锁。失败项保留证据与安全拒绝，不正式部署本实验分支。
