# 2026-10-23：M3 HDMI HDR、10-bit、420 与跳行缩放（离线）

接续 [VD1/VD2 与 NV12](2026-10-23-display-m3-video-planes.md)。本批接入标准
HDMI atomic state、HDR DRM infoframe、max bpc、Colorspace 和 YUV420，并补齐
4K NV12 → 1080p60 的逐行跳行读取。**新路径仅离线实现，HDR/BT.2020 有明确阻塞。**
中途按用户指令完成 [M2 第三窗口](2026-10-23-display-m2-window3.md)，随后恢复离线工作。
该窗口没有启用 M3 atomic-color 或视频层，不是这些新路径的物理验证。

## 实现与提交

| 提交 | 内容 |
|---|---|
| `74c6b03e1578b` | 按像素时钟、8/10 bpc 和 420 计算 PLL、链路分频与 TMDS |
| `778db592ba282` | 合入 M2 实测 pre-map / HPD 修复，补齐 M3 资源列表 |
| `f0c60b6dd4540` | atomic-color binding，保留旧资源列表描述 |
| `cf5dacb442ced` | 标准 HDMI state、HDR/AVI packet、色彩矩阵、10-bit/420 与 ACR |
| `be1ea339651db` | VD1/VD2 progressive vskip 与 modeset 后安全重建 MIF |
| `d76e5ce8acd41` | 根据物理窗口和厂商 T7 路由证据，拒绝尚未取得 HDR2 所有权的 BT.2020 |

内核功能分支为 `vim4-display-m3`。新功能由 M3 / M3-video DT 的
`amlogic,atomic-color` 显式启用；M2 DT 保持原有 8-bit YUV444 输出策略。
M2 通过项另合入正式源码 `vim4-kvm-7.3@2cc04af44e3d4`；M3 新路径没有合入正式分支。
没有修改部署锁、U-Boot 或应用，也没有正式部署。

`drm_bridge_connector` 的 HDMI 标志启用 `drm_hdmi_state_helper`，由标准 helper
按 EDID 协商格式、位深和 TMDS，并生成 AVI/HDR/vendor infoframe。驱动使用
connector 标准 `HDR_OUTPUT_METADATA`、`max bpc`、`Colorspace`、`Broadcast RGB`
和 color format 属性；没有另建私有 HDR ABI。传输格式和位深取自本次提交的
`connector_state->hdmi`，VPP、PLL、TX、PHY、SCDC 与音频使用同一选择。

| 属性 / 传输 | 本候选行为与限制 |
|---|---|
| max bpc | 8..10；EDID 不支持的深色由 helper 拒绝或降低实际 bpc |
| RGB444 | BT.709 转 RGB full；AUTO / FULL 为 full，LIMITED 拒绝 |
| YUV444 / YUV420 | limited；AVI YCC 范围声明 limited，不支持 YUV422；有效矩阵路由待核实 |
| Colorspace | Default / BT709_YCC / BT2020_YCC；Default 也使用 BT.709 |
| BT2020_YCC | 最终提交返回 `-EOPNOTSUPP`，日志说明需要独占 T7 OSD HDR2 |
| HDR metadata | 标准属性/校验/packet 已实现；因 BT.2020 路由未取得所有权，HDR 提交目前拒绝 |
| HDR 清除 | disable 清 DRM bank；HDR→SDR / metadata 改变触发 modeset 并更新 packets |
| 420-only | 主线 helper 根据 EDID 420-only 位限制为 420，水平像素及总周期须偶数 |
| SCDC | 按实际 TMDS：超过 340MHz 需 sink SCDC + scrambling，写配置失败保持静音 |

当前线性 RGB framebuffer 仍为 8-bit；10-bit 指 HDMI 传输位深，没有增加源缓冲精度。
没有 tone/gamut mapping 或 P010。解除 HDR2 门禁后，用户态仍须核对 sink 的 BT.2020
能力并提供按色域/EOTF 编码的内容；仅给 SDR 像素加 metadata 不能完成 HDR 转换。

## 厂商对照与寄存器所有权

硬件依据固定 `common_drivers@4cfb128d36f8511b2db1bd13c08d5704347ded49`：

- `hdmitx21/hw/hw_clk.c` 的 T7 `hdmitx21_set_clk()`、24/30-bit clock tables：
  10-bit 使用 VID PLL 6.25 分频，420 改变 OD、PNX / pixel 分频；没有复制 S5/S7 分支。
- `hdmitx21/hw/hdmi_tx_hw.c:config_hdmi21_tx()`：P2T deep-color、输入 mask、
  GCP、CSC preset 0x65、T7 formatter 和 HDMI_SETTING 的 pre/post 映射。
- `hdmi_tx_pktmgmt.c`：AVI bank 0、audio bank 2、vendor bank 5、DRM bank 6；
  packet mutex 串行写 bank，清 HDR 不碰音频 bank。
- `osd_reg.h` / `osd_hw.c` 与 `amvecm/amcsc.c` 提供通用 0x3910..0x391d
  矩阵和 BT.709 / BT.2020 limited 系数及负数舍入宏，host 比较确实一致。
  但 `osd_fb.c:osd_t7` 没有设置 `osd_rgb2yuv=1`；初始化不会走
  `set_vpp_osd1_rgb2yuv()`。M2 窗口读回该矩阵全零，不能视为有效 T7 转换。
- `amvecm/set_hdr2_v0.c:hdr_func()` 对 RGB_OSD / HDR_BYPASS 选择 HDR2 输入矩阵，
  `set_hdr_matrix()` 依据 OSD1/2/3 选择各自的寄存器。SDR_HDR 则涉及 LUT / gamut。
  这不是把通用矩阵系数写入一次即可替代的生命周期。

因此本轮**没有完成可用的 HDR/BT.2020 输出**，没有把未转换像素标为 BT.2020。
最终 guard 保留标准属性、blob 校验和独立 DRM packet bank 实现，但有效 HDR 提交
明确失败。下一步需要逐 OSD 证明 T7 HDR2 路由（含 Mali/Dolby bypass）、SRAM/时钟
所有权、继承 LUT 的关闭/初始化顺序、8/10-bit 数值域与 plane 混合位置，再实现
vendor 参数对照和物理读回；不能挪用 VDIN HDR 核、S5 寄存器或仅按矩阵地址猜测。
已取得物理相对颜色证据的 M2 路径保留，尚不能宣称矩阵与 AVI 的完整物理验收。

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

厂商 `vpp_process_speed_check()` 对未压缩 4K 下缩、输出超过 30Hz 要求 vskip。
`vd1_set_dcu()` / `vdx_set_dcu()` 的逐行路径使用 Y/UV 四个 repeat pattern=0x8、loop=0。
仅实现 vskip=1：MIF 保持完整 DMA 范围和 stride，PPS / HDR input / VPP 输入高度减半。
crop y / 高度须 4 行对齐以保留完整色度行对；其他 skip 因子拒绝。

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
最终另验证合法 HDR 与 BT.2020 仍因 HDR2 门禁返回 `-EOPNOTSUPP`，并确认
无 HDR 的 BT.709 10-bit/420 继续通过 atomic check。

`test_t7_video.py` 执行厂商两路 DCU 原始块与实际 MIF builder，128 组参数覆盖
Y/UV repeat、地址、formatter、stride 和拒绝边界。video KMS 测试覆盖双路跳行、
有效输入高度、完整 DMA scope、4K30/60 切换，以及 modeset 强制两阶段重建。
既有 RMFB、60/60 OSD、fence/退休、SRAM、producer 布局、CEC/RX/Wave5 回归继续运行。

完整构建、strict checkpatch、artifact 哈希与主仓测试见
[验证与批量清单](2026-10-23-display-m3-hdmi-validation.md)。

## P010 / AFBC 继续保留的门禁

P010 仍未公开：T7 `video_hw.c` 没有明确的 bit16 / P010 unpack；已知 bit7 实现
在 `video_hw_s5.c`，不能移给 T7。需要 T7 MIF 对高 10-bit、低填充、endian、
16-bit stride 的寄存器依据，以及 VDIN/Wave5/vdec 实际 producer 布局对照。

AFBC 仍仅记录：需可验证的 configuration-swapped / surfaces-completed 代际完成，
包括陈旧 IRQ、多 surface、双 decoder core、disable 排空及故障固定引用合同。
surface enable 清零、raw error status 和普通 MIF 额外 vsync 均不能证明 decoder idle。
在这些证据补齐前不公开 Mali AFBC modifier。

M2 + M3 的无需用户 / 需用户在场项目分列在
[一次性启动清单](2026-10-23-display-m3-hdmi-validation.md#m2--m3-一次性启动批量上板清单)。
