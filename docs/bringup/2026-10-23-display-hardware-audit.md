# 2026-10-23：T7 显示硬件与源码明细

本页是 [显示可行性调查](2026-10-23-display-feasibility.md) 的按需明细。
结论：T7 保留 Meson VPU 的部分寄存器与管线概念，但 OSD 寻址、scaler、blend、
VENC mux、时钟和 TX 均存在实质差异。推荐 meson-drm 的 T7 分支加独立 TX bridge；
不需要移植整套厂商 media/DRM 框架。兼容性以下述源码为依据，未做寄存器上板探测。

## 引用约定与厂商栈

路径 `V/` 指 VM `~/src/linux/common_drivers`，固定
`4cfb128d36f8511b2db1bd13c08d5704347ded49`；
[公开源码根](https://github.com/vim4-kvm/common_drivers/tree/4cfb128d36f8511b2db1bd13c08d5704347ded49)。
`D/` 为 V 下 `drivers/media/vout/hdmitx21/`；`M/` 为 7.3 下 `drivers/gpu/drm/meson/`，
固定 [0196fe22ecf0 源码根](https://github.com/vim4-kvm/linux/tree/0196fe22ecf0104d96b7ef0fa497ca2317bd20bb)。
行号对应上述快照；实现段不一定逐行适用于 T7。

厂商桌面路径概念为 framebuffer/DRM plane→OSD MIF→scaler/blend/VIU/VPP→
ENC0 或 ENC2 的 VENC→HDMI-TX TOP/COR→模拟 PHY。
VD1/VD2 等视频层还接 vframe/video_sink，与 OSD 合成；HDMI 音频另由 ASoC/I²S
送入 TX AIP/ACR/packet。显示 VPU 与 Wave521C 的“VPU”称呼不同，不能混用寄存器或固件。

| 模块 | 厂商关键文件 / 行号 | 调查结果 |
|---|---|---|
| 资源及入口 | `V/arch/arm64/boot/dts/amlogic/mesont7.dtsi:2548–2579,2758–2780`；`D/Makefile:3–23` | T7 compatible 为 amhdmitx-t7，走 hdmitx21；VPU 管理与 TX/OSD/video_sink 分散在不同驱动 |
| VPU 时钟/内存 | `V/drivers/media/common/vpu/vpu.c:2107–2148,2792`；`vpu_ctrl.h:493–498` | T7 表选择 CLKCTRL、PWRCTRL_MEM_PD5…9、VPU_HDMI/VI_CLK1/VI_CLK2；不是 G12A 单 HIU |
| OSD / VIU | `V/drivers/media/osd/osd_hw.c:577–805`；`osd_reg.h:48,478,1312,1788` | T7 单独寄存器表，OSD1 scaler 起于 word 0x5a00；OSD1 线性基址寄存器 0x1a14，mux 0x271a、VENC ctrl 0x1cef |
| 厂商 DRM OSD | `V/drivers/drm/vpu-hw/meson_vpu_osd_mif.c:1251,1504–1551,1880,2011` | after-v7 的线性地址路径与 T7 ops，不能照搬 G12A canvas-only |
| VPP blend / VD | `V/drivers/drm/vpu-hw/meson_vpu_postblend.c:440,1189,1272`；`V/drivers/media/video_sink/video_hw.c:1204,1283,2223,2785` | T7 专用 postblend；VD 与缩放还有独立分支。VD 多层、AFBC、HDR/PQ 不属于最小 RGB OSD 里程碑 |
| VENC | `D/hw/enc_cfg_hw.c:415,645,770–783`；`D/hw/hdmi_tx_hw.c:1313–1345` | ENCP/ENCI 时序、编码器选择、pixel/FE/PNX 分频；enc_idx 选择与安全世界有关 |
| TX / DDC / packet | `D/hw/hdmi_tx_hw.c:784–825,1180–1185,1313–1345`；`hw/hdmi_tx_ddc.c`；`hdmi_tx_infoframe.c` | 独立 TOP/COR，DDC/SCDC、AVI、audio packet；不是旧 dw-hdmi 的 FC_* / PHY API |
| PHY | `D/hw/hw_t7.c:417–456`；`D/hw/hdmi_tx_hw.c:784–825` | 模拟 ANACTRL PHY，按 TMDS 档位选参数、脉冲 reset；不能把 T7 当 G12A PHY |
| 时钟 | `D/hw/hw_t7.c:35–85,159,383–413`；`D/hw/hw_clk.c:91–171,390–565,1586` | HDMIPLL 的 VCO/OD、VID_PLL divider、VID_CLK0、ENC0_HDMI、TX audio/sys/prif 等多级门控 |
| HDCP | `D/hw/hdcp.c:27–109,161`；`D/hdmi_tx_main.c:4907–4908,5352–5428` | 1.4/2.2 key/result 走安全调用，tee_comm_hdcp 接收 key-ready 通知；普通无保护桌面可先不实现 HDCP |
| 电源域 | `V/drivers/power/sec_power_domain.c:54–69,259–272` | VPU_HDMI、VI_CLK1、VI_CLK2 为 INIT_ON+ALWAYS_ON，经安全电源调用；RX 独立域也常开 |

注意 `vpu_power.c:255–273` 中 `vpu_power_on_new()` 的实际 SMC 有 **SC2 条件**；
不能仅因 T7 表引用该函数就说 T7 在这里完成上电。T7 的域管理应以上表 sec_power_domain 为准。

### MMIO 基址与单位

权威板级映射是 `V/arch/arm64/boot/dts/amlogic/mesont7.dtsi:2564–2579`；
7.3 对应 `arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi:1955–1965,2012–2025`。

| 块 | T7 物理地址 / 长度 | 说明 |
|---|---|---|
| VCBUS / VPU | `0xff000000 / 0x40000` | OSD/VIU/VPP/VENC/VDIN 等寄存器空间；word index 转 byte offset 要 `index << 2`。例如 scaler 0x5a00→0xff016800 |
| HDMI COR | `0xfe380000 / 0x10000` | 8-bit byte offset，不能再左移两位 |
| HDMI TOP | `0xfe300000 / 0x10000` | 32-bit byte offset |
| ANACTRL | `0xfe008000 / 0x2000` | HDMIPLL CTRL0 offset 0x1c0，PHY CTRL0 offset 0x200 |
| CLKCTRL | `0xfe000000 / 0x2000` | ENC0_HDMI offset 0xd4，VID_PLL_CLK0_DIV offset 0xe4 |
| PWRCTRL / SYSCTRL | `0xfe00c000 / 0x2000`；`0xfe010000 / 0x2000` | 7.3 VPU 节点只映射其所需子区间 |
| RESET / PAD | `0xfe002000 / 0x2000`；`0xfe004000 / 0x200` | TX/PHY reset；HPD/DDC 引脚 GPIOW15/14/13 |

`D/hw/register.h:54,58,98,107` 定义上述寄存器；`hw/hw_t7.c:426–432` 还明确 TX、
PHY、vid_pll_div、TX APB reset 位。厂商 VPU 管理节点只映射 VCBUS 的 0xf000 子区间，
**不表示整个 T7 VPU 只有 0xf000**；TX 与当前 DRM/VDIN 使用完整 0x40000。
IRQ 分开：显示 vsync SPI197，TX HPD SPI204，当前 VDIN0 SPI213。

### 时钟、SMC 与固件边界

1080p60 RGB8 的像素/TMDS 时钟为 148.5MHz。T7 显示代码从 HDMI PLL 经 OD、
VID_PLL_CLK0_DIV、VID_CLK0_CTRL/DIV 与 ENC0_HDMI 分配 ENCP、pixel、FE、PNX。
厂商 `hw_clk.c:91–145` 另外设置 `cts_hdmitx_aud_clk`、`cts_hdmitx_sys_clk`、
`cts_hdmitx_prif_clk`/200m 门；这些名称不是可以省略的同义词，也不都是 Linux clk_summary
可独立观察的 provider。音频 ACR 的 N/CTS 是包内时钟恢复参数，与 `cts_*` gate 命名分别核对。

**HDCP 可不做，但安全调用不能假定全可删除。**

- `D/hw/reg_ops.c:76–124,201–250`：TOP 32-bit、COR 8-bit 的厂商读写分别走
  `0x82000018/0x82000019` SMC；VCBUS/模拟寄存器另有直接 MMIO 路径。
- `D/hw/hdmi_tx_hw.c:1180–1185` 调用 HDCPTX_IOOPR/CONF_ENC_IDX；
  7.3 `M/meson_venc.c:20–22,1920–1936` 保留 `0x820000ab, op=9, set=1, ENC0`。
- 7.3 `M/meson_hdmitx21.c:188–205` 却直接 readl/readb/writel/writeb TOP/COR。
  这与厂商访问方法不同，需要核对当前 BL31 的非安全访问许可及覆盖范围。
  当前 bridge probe 已做初始化，未见这一步导致启动失败；尚未证明全部寄存器读写有效。
  不以无 HDCP 推导“无需 SMC”，也不在无人现场用 devmem 做试错。
- 7.3 genpd `drivers/pmdomain/amlogic/meson-secure-pwrc.c:61–90,340–351`
  仍通过 meson_sm 管理安全域，并常开三个显示域。HDMI PLL 的 CLK_IGNORE_UNUSED
  属于保状态措施，尚未构成完整的 CCF/runtime PM 生命周期设计。
- 本轮审查的 hdmitx21 基本显示路径未发现需要 Linux request_firmware 加载的专用显示
  microcode；这不代表无 BL31 依赖。HDCP key/TEE 通知、受保护视频及 Dolby 等另行处理。
  未审查闭源 BL31 内部实现，不承诺旧版固件均兼容；沿用已部署固件，不提出刷写要求。

## 原生 G12A/SM1 与 T7 逐项比较

G12A 依据上游 v7.3：`meson_drv.c:537–550`、`meson_dw_hdmi.c:35–70`；
T7 依据上面固定 7.3 的候选代码和厂商实现。

| 项目 | G12A/SM1 | T7 / 推荐处理 |
|---|---|---|
| DRM 对象 | 单 CRTC、OSD1 primary、VD1 overlay、atomic/GEM DMA、RDMA/vblank | 可扩展这些对象；新写整套 KMS 不划算。M1 先只启 OSD1，overlay 单独验收 |
| 寄存器控制 | HHI/syscon 下 PLL/PHY 等 | 拆为 ANA/CLK/PWR/SYS/RESET；`M/meson_drv.c:253–346`。需明确各块所有者 |
| OSD MIF | canvas 为普通扫描输出提供地址 | T7 要线性地址和 stride/16；保留部分 OSD1 控制寄存器，`M/meson_crtc.c:405–414`；不是全块兼容 |
| OSD scaler | G12A 的 VPP_OSD_* 地址 | T7 搬到 0x5a00；`M/meson_drv.h:204–208` 映射，不应裸复用 G12A 地址 |
| VIU/VPP blend | G12A blend/矩阵布局 | 部分控制可复用，但 T7 source 4 选 OSD1、postblend RGB、关闭 OSD RGB→YUV；`meson_crtc.c:291–301`、`meson_viu.c:430`、`meson_vpp.c:98–103` |
| VD1/VD2 | 旧 VD register offset、canvas/AFBC 管线 | S4/T7 layout 分支可作参考；不能把 RGB OSD 可用推广为所有 YUV plane/AFBC 可用，需逐格式验证 |
| VENC | ENCI/ENCP timing、VIU→encoder mux、HDMI_SETTING | 沿用部分时序寄存器/表；T7 mux 0x3c、VENC_CTRL/HDMI_SETTING 新位义、SMC 选 ENC0，见 `meson_vpp.c:36–45`、`meson_venc.c:1916–1940` |
| PLL / pixel clock | G12A HHI HDMI PLL、VID divider | T7 ANACTRL PLL 与 ENC0_HDMI divider；`meson_vclk.c:125–141,913–923,1243–1247` 用 5.94GHz VCO 策略。不能套旧 PLL 常量 |
| TX controller | Synopsys dw-hdmi + Amlogic TOP/PHY | T7 hdmitx21 TOP/COR、DDC、AIP/TPI 寄存器，**不是 dw-hdmi**；独立 bridge 已存在。仅据 IVCTX 等命名不能进一步断言第三方 IP 厂商 |
| PHY / SCDC | 旧 PHY ops，dw-hdmi DDC/packet 框架 | T7 参数独立；`meson_hdmitx21.c:454–483,810–825`，>340MHz 需 sink scrambling；首期 148.5MHz 避开该分支 |
| AFBC / reset | G12A decoder reset | T7 复用会命中 OSD1；`meson_drv.c:674–677` 不设 afbcd_ops。首期禁 AFBC，不为桌面性能先开压缩 |
| 音频 | dw-hdmi I²S codec + ASoC glue | TX bridge audio callbacks、N/CTS/InfoFrame；`meson_hdmitx21.c:597–677,984–988`；TOHDMITX MCLK/2，`sound/soc/meson/g12a-tohdmitx.c:253–261` |

`meson_hdmitx21.c:727–738` 限制 ≤600MHz 和高时钟 scrambling；`982` 禁 interlace。
VENC 表 `meson_venc.c:1161–1180` 列 CEA VIC，不能把 bridge 的时钟上限当作任意 CVT 模式支持。
音频配置 `597–650` 固定 24-bit 的寄存器序列，`668` 只接受 I²S/2ch；不同容器位宽/速率
需要实测，不宣称 SPDIF、多声道、压缩音频直通或 eARC 已支持。

## 代码规模与集成边界

以下按 VM 固定厂商树递归统计 `.c/.h` 物理行，含注释、寄存器表和其他 SoC，**不是 T7
专属有效代码量，也不是计划移植量**。目录之间未作跨路径语义去重，不能据总和估计工期。

| 厂商目录（V 下） | 文件 / 行数 |
|---|---|
| drivers/media/vout/hdmitx21 | 35 / 28,352 |
| drivers/media/common/vpu | 10 / 6,890 |
| drivers/media/osd | 29 / 37,207 |
| drivers/media/video_sink | 42 / 96,900 |
| drivers/drm | 67 / 34,312 |

示例：TX `hdmi_tx_main.c` 5428 行、`hw/hdmi_tx_hw.c` 4650 行、`hw/hw_clk.c` 1705 行、
`hw/hw_t7.c` 501 行、`hdmi_tx_hdcp.c` 2073 行；后者大量内容不属于无保护桌面最小路径。
不建议复制 video_sink/vframe/PQ/ION/sysfs 框架进入 7.3。
当前分支相对原生 v7.3 的整个 `drivers/gpu/drm/meson` 差异为 22 文件、+3584/-685 行，
其中包含 S4 和其他改动，不能全归 T7。单独 T7 bridge 为 1014 行。
代码规模与 probe 均不构成显示、声音或共存验收。

## 结束复核与验证边界

04:00–04:01 UTC 只读复核：build ID 仍为 `3a61b75bccf8c46e9411dee92928999884bbfc7f`，
notes 前后相同；One-KVM/manager active，UDC configured，hidg0…3 存在，taint=0。
VPU disabled，TX 绑定 meson-hdmitx21，无 fb/HDMI connector，ALSA 仅 VIM4HDMIRX。
chosen 的 BL33 仍为 `0d5a3d7848`，BL31 `1.3.2,2dd964006`。

**共享板期间发生启动变化**：首次 boot ID `fcca52f8-0d54-4fd9-9d0d-8296934b341d`，
结束为 `4c9f3ff2-a2a0-495c-9268-f7ef48bf2731`；journal 显示新启动始于 03:54:32 UTC。
“同一次启动”断言因此失败；本任务无板端写命令，无法据此归因；前后均为指定内核基线。
未重新发送 HID 报告或验收应用二进制版本。

离线全套 `python3 -m unittest discover -s tests -p 'test_*.py'`：184 项，9 skipped，OK。
worktree 缺子仓库，相关检查跳过；文档链接、索引和体积通过。
初轮超 12000 字节失败，精简后全套通过；日志 `logs/display-feasibility/tests.txt`。
