# 对照依据与复核方法

结论以固定源码与已提交上板记录为准。本轮离线审查，不联网补充产品规格；“源码启用”、
“模块加载”和“硬件验收”是三种不同证据。节点全集见 [vendor-nodes.tsv](vendor-nodes.tsv)。
能力行、统计口径与实施优先级见 [主表](../vendor-parity.md)。

## 固定版本

| 对象 | 本轮只读版本 |
|---|---|
| V，厂商主内核 | VM `~/src/linux`，`80a07ad5406d57855c996285ae75a50a1b9147ae` |
| C，厂商 common_drivers | VM `~/src/linux/common_drivers`，`4cfb128d36f8511b2db1bd13c08d5704347ded49`，查询时干净 |
| E，7.3 比较基线 | `47878a0c611d1e1deb3699c4f225963a37a218c0`，M0 已部署证据，非 VM 目录当前 HEAD |
| E8，最新正式增量 | `aa2f875bec2fc7c9a4952fccb9dcaa6fbfc4aa64` / manager `9b141c58`；仅Wave5能力行叠加，非重新验收整表 |
| B，启动固件基线 | U-Boot `0d5a3d7848377c0093ecdfb15de80cf2bf83e928`，pd-handoff |
| 用户态比较基线 | One-KVM `382efb70`；manager `4ea7484` |

VM 原 7.3 工作树查询时 HEAD 是 `0196fe22ecf01`，因此以 `git show E:path` / `git archive E`
读固定内容，没有切分支、修改源码或构建。厂商芯片行为只取 V/C，不以产品宣传推导。
下表所有缩写的 `:数字` 都是对应固定文件的源码行号。

## vendor

| 引用 | 固定文件与关键行；路径相对 C，V 主内核除外 |
|---|---|
| V0 | [kvim4.dts](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/arch/arm64/boot/dts/amlogic/kvim4.dts)：8–13 include；524–550 旧相机；610 声卡；1630 ISP；1968 IR 最终启用 |
| V1 | [kvim4n.dts](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/arch/arm64/boot/dts/amlogic/kvim4n.dts)：541 RX；595–778 九个 DAI；977–1382 TDM/PDM/SPDIF/ASRC/VAD；1386 eARC disabled；1390 USB；1444 PCIe；1451 I²C；1563 MCU/RTC；1596 MMC；1681 网口；1736 NOR；1788 DRM；1848 TX；1858 VDIN；2070 IR |
| V2 | [mesont7c.dtsi](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/arch/arm64/boot/dts/amlogic/mesont7c.dtsi)：302 PM；330 secmon；340 OP-TEE；380 域；386 ADLA；433/456 DSP；1226 cpufreq；1969 PCIe；2203 CSI/ISP；2270 VDEC；2438 CEC；2474 crypto；2501 RNG；2518 codec_io；2541 JPEG；2566 MultiEnc；3317 efuse |
| V2o | [mesont7.dtsi](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/arch/arm64/boot/dts/amlogic/mesont7.dtsi)：386–480 四个 NNA wrapper；502/529 DSP；2890–2975 六温区；3193 VDIN；3354 GE2D；3400/3417 GDC；3430 mailbox；3484 efuse；4744 GPU 频率表 |
| V3 | [media_modules/Kconfig](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/drivers/media_modules/Kconfig)：8–147 codec；149 AVC、155 HEVC、161 MULTI、167 JPEG、179 COMMON、191 V4L_DEC |
| V4 | [decoder_cpu_ver_info.c](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/drivers/media_modules/common/chips/decoder_cpu_ver_info.c#L237)：T7 平台表及格式掩码；不能从整个 Kconfig 反推 T7 所有 codec |
| V5 | [vpu_multi.c](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c)：324 上电复位；436 空 HWReset；1390 IRQ 等待；3421 resume。复位差异见 [Wave5 审查](../bringup/2026-10-23-wave5-recovery.md) |
| V6 | [khadas-panel.dtsi](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/arch/arm64/boot/dts/amlogic/khadas-panel.dtsi)：8 LCD0、1090 背光、1186 local dimming 启用；1435 LCD1、1926 LCD2 禁用 |
| V7 | [ADLA platform](https://github.com/vim4-kvm/common_drivers/blob/4cfb128d36f8511b2db1bd13c08d5704347ded49/drivers/adla/kmd/drv/port/platform/linux/adlak_platform_device.c#L54)：`amlogic,adla`；drivers/Makefile:68 无条件进入 adla。`drivers/npu/Kconfig:3` 的 AMLOGIC_NPU 是另一套驱动，不能混为一谈 |
| V8 | V 主内核 [mali_clock.c](https://github.com/vim4-kvm/linux/blob/80a07ad5406d57855c996285ae75a50a1b9147ae/drivers/gpu/arm/midgard/platform/devicetree/mali_clock.c)，逐频调压证据不足；精确语义与启动电压见 [GPU 电压审查](../bringup/2026-10-22-p2-gpu-voltage.md) |

## edge

以下路径相对 E；引用到目录时，能力表另给具体文件与行号。

| 引用 | 固定 7.3 路径与边界 |
|---|---|
| E0 | [VIM4 DTS](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4.dts)：109 GPU OPP 无电压；481 sound；662 I²C MCU/RTC；704 PCIe；770 NOR disabled；887 UART/BT |
| E1 | [T7 DTSI](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi)：493 PCIe；535 RNG；969 USB；1719 FRDDR；1824 SPDIF；1903 TOHDMITX；1994 RX；2012 TX |
| E2 | [专用采集 DTS](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dts)：25 TEE；33 JPEG；47 Wave；65 VDIN；79 禁用 native VPU；[audio-test DTS](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-audio-test.dts#L34) 删除通用 sound，只保留 RX/TODDR；[display-m0 DTS](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m0.dts) 继承这条链 |
| E3 | [t7-hdmirx](https://github.com/vim4-kvm/linux/tree/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/media/platform/amlogic/t7-hdmirx)：`t7-hdmirx.c:903` 色彩/12bit 解析；949 HLG 拒绝；977 测量；1035 隔行拒绝；1260 音频；`t7-vdin-test.c:1499` NV12/RGB24 输出 |
| E4 | [Wave5](https://github.com/vim4-kvm/linux/tree/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/media/platform/chips-media/wave5)：`wave5-vpu-enc.c:33` HEVC 八像素步进、1648 无 job_abort；`wave5-vpu.c:194` probe 固件加载。隔离/复位证据见专项记录，不能把候选当已部署 |
| E5 | [T7 JPEG](https://github.com/vim4-kvm/linux/tree/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/media/platform/amlogic/t7-jpeg)，V4L2 M2M、DMA-buf；[VDEC TODO](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/media/platform/amlogic/vdec/TODO#L3) 仍列 T7 与更多格式 |
| E6 | [CRG](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/usb/gadget/udc/crg/crg_udc.c#L4689)：system suspend 返回 EBUSY；[secure genpd](https://github.com/vim4-kvm/linux/blob/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/pmdomain/amlogic/meson-secure-pwrc.c#L332)：VPU/USB/MMC 多域 ALWAYS_ON |
| E7 | [meson DRM](https://github.com/vim4-kvm/linux/tree/47878a0c611d1e1deb3699c4f225963a37a218c0/drivers/gpu/drm/meson)：T7 native 候选、TMDS ≤600MHz/RGB8/双声道/无 HDCP；[配置](../../packaging/kernel-edge/uhd1.config) 是配方，不是运行时验收 |
| E8 | [最新Wave5隔离](https://github.com/vim4-kvm/linux/blob/aa2f875bec2fc7c9a4952fccb9dcaa6fbfc4aa64/drivers/media/platform/chips-media/wave5/wave5-isolation.c#L115)：job_abort/watchdog、隔离状态与引用保留；enc.c:1685注册job_abort。`git diff --name-only E aa2f875`只列Wave5与相关ABI文档，原DT/RX/ASoC未变；[正式窗口](../bringup/2026-10-23-wave5-isolation-final.md)十次软件超时注入/重启恢复和九类回归，不含真实固件挂死/运行时重载 |

## 节点与模块清点

TSV 保留两个板型所有带 compatible 的节点，compatible_source记录C树路径/行号，
多处同名定义列候选位置；最终status取展开树。包括 disabled、reserved-memory、CPU、
总线与 OPP；不把基础设施节点数当功能数量。缺省 status 按 okay，父 disabled 覆盖子 okay。
`disable` 也不算启用。最终结果：kvim4 274 个节点，242 enabled / 32 disabled；
kvim4n 261 个，227 enabled / 34 disabled。IR 的前一次 disabled 被尾部 okay 覆盖；
eARC、loopback B、SPIFC/NOR、SPICC 均没有因子节点或配置开关被误算启用。

在厂商树干净的条件下，按其 `.kvim4n.dtb.cmd` 的 include 路径重新展开，输出只写 `/tmp`：

```sh
cd /home/deepdream/src/linux
gcc -E -nostdinc -I./common_drivers/include -I./scripts/dtc/include-prefixes \
  -undef -D__DTS__ -x assembler-with-cpp \
  common_drivers/arch/arm64/boot/dts/amlogic/kvim4n.dts |
  ./scripts/dtc/dtc -q -I dts -O dts -o /tmp/vendor-parity-kvim4n.dts -
# kvim4 同法；按树层级抽取 path/compatible/status/effective_status，去掉标签。
```

配置交叉核对 VM `~/src/linux/.config:6914–7801`（生成文件，非源码版本锁）：
MEDIA_MODULE、MULTI_DEC、HDMITX21、GE2D、DEINTERLACE、VDIN、TVIN_HDMI、
DOLBYVISION、VENC_MULTI/JPEG、各 codec、SND_SOC_AUGE、AUDIO_DSP、NPU、
PM、TEE/OPTEE、CRYPTO_DMA、FREERTOS_T7 等均启用。跨 SoC 的 DSC/AVS3/REAL
等开关只证明编译选项，是否计入 T7 要再看 V4 与节点匹配。

旧 5.15 真实加载证据为本地 `logs/uart-mic-crash.log:91–92`、
`logs/mjpeg-hardware/kernel-after.log:23–25` 的 `Modules linked in`；原始日志不入库，
关联现场见 [USB/采集链](../bringup/2026-10-12-capture-encode-usb-gadget.md)、
[JPEG 实测](../bringup/2026-10-14-mjpeg-hardware-4k-throughput.md) 与 [厂商内核](../kernel.md)。
为防止结论依赖忽略目录，保留与本表有关的模块名摘录：

| 子系统 | 实际加载的模块（省略 E/O 标记；加载不等于功能通过） |
|---|---|
| 显示/采集 | aml_drm、aml_media、vfm_cap、media_clock、video_framerate_adapter |
| 编码 | amvenc_multi、jpegenc、encoder_common |
| 解码 | decoder_common、stream_input、firmware、amvdec_ports；mh264/mh264_v4l、h264mvc、h265/h265_v4l、vp9/vp9_v4l、av1/av1_v4l、mmpeg12/mmpeg12_v4l、mmpeg4/mmpeg4_v4l、mmjpeg/mmjpeg_v4l、vc1、mavs/mavs_v4l、avs2/avs2_v4l/avs2_fb_v4l、avs3_v4l |
| 音频 | amlogic_snd_soc、amlogic_audio_utils、snd_codec_dummy/t9015/tl1/ad82128/pa1/tas5805/tas5707/ad82584f |
| GPU/NPU/相机 | mali_kbase、adla_core、amlcam、amlsens、dw9714、amlogic_camera |
| USB/网络/存储 | amlogic_usb、dwc_otg、dhd、amlogic_wireless、stmmac、dwmac_meson、amlogic_pcie_v2_host/v3_host、amlogic_mmc、cqhci |
| PM/安全/调试 | khadas_mcu、amlogic_thermal/pm/power/cpufreq、optee、tee、amlogic_tee、amlogic_rng、amlogic_efuse_unifykey、amlogic_seckey、amlogic_crypto_dma、aml_smmu、amlogic_memory_debug、amlogic_debug_iotrace、bl40_module |
| 外设 | amlogic_input/irblaster/adc/i2c/spi/rtc/watchdog/mailbox/gpio/pwm/pinctrl_soc_t7、amlogic_led、amlogic_jtag |

## 本轮板端边界

本轮只执行 SSH 读 uname、service 状态、UDC、HID 节点、taint、kernel notes 与 `/boot`、
模块目录列表。没有读裸寄存器、开视频/音频流、采样性能、重启、改服务或固件。
`readelf -n /sys/kernel/notes` 报非 ELF，随后用 Python 按原始 note 的 4 字节对齐解析
GNU type 3，结果如下：

```text
release=7.3.0-vim4kvm-uhd1+
build_id=7b8372b894c98ffae12e636a325c86f2b6c85e00
one-kvm=active; vim4-manager=active; UDC=configured; taint=0
/dev/hidg0..3 存在
```

并行任务已改变运行版本；本地仍在更新的
`docs/bringup/2026-10-23-kvm-audio-capture-stability.md` 也记录了该基线冲突。
以上不是指定 M0 的复验；本轮无部署，故无恢复操作，也未重新证明真实 HID 输入。
本表以固定 M0 加E8明确增量计数；E03仍为部分对齐。以后改基线应逐行更新证据，
不能只改页首版本号。
