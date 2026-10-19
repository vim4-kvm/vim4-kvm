# 7.3 USB 与音视频适配拆解

2026-10-19 对固定 7.3 源码和 common_drivers `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`
做静态核对，并对照首次启动日志。结论：USB 缺少 CRG UDC 实现与设备树接入，
也缺 configfs 功能配置；HDMI 输入和编码需要独立适配，不能靠启用同名驱动解决。
本轮不修改板上配置，仍运行 5.15。硬件证据见 [首次启动](bringup/2026-10-19-edge-firstboot.md)。

## USB：已定位的缺口

7.3 `arch/arm64/boot/dts/amlogic/amlogic-t7.dtsi` 的 usb_comb 虽然声明 otg，
两个子设备却均为 `amlogic,t7-xhci`，分别映射 fdd00000/fde00000。
启动日志也只有这两个 xHCI host，drivers/usb 中没有厂商 CRG UDC 的匹配实现。
因此仅设置 dr_mode=peripheral 或加载 DWC3 gadget 都不能产生所需 UDC。

原最终配置 USB_GADGET=y，但 USB_CONFIGFS 未启用。现已在 edge.config 加入
USB_CONFIGFS=m，以及 HID、NCM、ECM、RNDIS、mass storage、UAC2。
选择范围来自 tools/kvm-gadget.sh 与现有应用 USB profile；不自动绑定 gadget。

独立输出目录 VM `~/build/kernel-edge-gadget` 完整构建 Image、dtbs、modules 通过，
日志无 warning/error。已用 modinfo 核对 libcomposite 与六个功能模块及 vermagic。
最终配置 SHA-256 为 `28d6d7587ea0cda7cb350056c3f4656839a9c54156267411cc57248aff2d9daa`；
Image 为 `904537f47bce8085ca720dd05e8a3f933d5d58a7261978622db1e402a40bc1e5`，
DTB 与首次构建的原始产物一致。详细 build.json 留在该输出目录，主仓库日志为
`logs/kernel-edge/gadget-build.log`、`gadget-artifacts.log`、`gadget-tests.log`。
离线测试 83 项通过、4 项跳过；新产物尚未安装或上板，不能混用首次测试的模块目录。

厂商入口为 common_drivers/drivers/usb/crg/crg_udc.c、crg_udc.h、crg_usbphy.c，
角色管理在 crg_drd.c 和 drivers/usb/crgdrdphy/。
kvim4n.dts 启用 crg_udc_2；mesont7.dtsi 给出 fdd00000/1 MiB、SPI 131、
PHY 控制地址 fe03a020、phy-id=1、usb_general 时钟。主线 host 占用同一 MMIO/IRQ，
设备端接入必须避免两者同时驱动；厂商与新 DTS 的 IRQ 触发类型也不同，需要核对硬件。

移植顺序：

1. 抽出 UDC 的端点、TRB、事件环实现；保持版权及已有 IRQ/解绑同步修复。
   当前驱动复制 configfs 私有 struct gadget_info，并直接操作其锁和 gadget_driver；
   新驱动必须移除这种内部结构依赖，让用户空间通过标准 configfs 绑定。
2. 将 usb-v2/usbtype、amlogic_crg_device_usb2_init/shutdown 和 crg_clk_* 依赖
   接到新内核的 PHY、clock、reset、power-domain 生命周期，明确共享寄存器归属。
   不能同时让厂商代码和 dwc3-meson-g12a glue 修改 PHY/复位。
3. 先做固定 peripheral 模式及专用测试 DTB，确认板上 PHY 路由与供电；
   稳定后再接 USB role switch。PD 协商与 gadget 控制器分别验证。
4. 先验 UDC probe/卸载和主机枚举，再验实际键鼠、存储、UAC2；
   覆盖持有 hidg fd 时解绑、重新绑定、SET_ADDRESS、总线复位和错误恢复。

5.15 历史重连修复不可丢失：gadget.irq 登记、udc_async_callbacks 在锁内控制，
禁用回调期间不处理新 SETUP/补发 STALL，不能直接丢弃硬件仍持有的请求链表。
这些要求不表示把旧源码复制到 7.3 后已经成立，须重新审查和实测。

## HDMI 输入、编码与音频依赖

| 功能 | 当前厂商实现入口 | 主要依赖 / 新内核缺口 |
|---|---|---|
| HDMI RX | drivers/media/vin/tvin/hdmirx/ | PHY、EDID/HPD、信号检测、时钟及 TVIN 接口；主线 snps_hdmirx 当前匹配 rk3588，并无 T7 接入 |
| VDIN | drivers/media/vin/tvin/vdin/ | codec_mm、VPU、VFM、canvas/帧路由和中断；需先建立连续 DMA 采集 |
| DMA-buf 输出 | drivers/media/vfm_cap/vfm_cap.c | VFM provider/receiver、codec_mm；必须保留缓冲持有和 CPU 同步语义 |
| Wave521 编码 | drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c | codec_mm、canvas、CPU 检测、厂商电源域及 vdec 电源辅助接口，现有 amvenc_multi 用户态 ABI |
| HDMI 输入音频 | sound/soc/amlogic/auge/tdm.c | hdmirx/hdmirx_b 输入源、RX 音频状态、TDM DMA 与路由；输出声卡注册不能证明输入可用 |

7.3 已有 chips-media/wave5 编解码驱动，但 wave5-vpu.c 当前 OF 表仅匹配
ti,j721s2-wave521c。需核实 T7 的寄存器、固件、电源和 DMA 接口后才能决定复用。
若改用标准 V4L2 M2M，还需改现有 amlvenc 用户态接入，不能假定旧 ioctl ABI 可用。

先完成独立 HDMI 输入取帧，再接编码，最后接音频与应用。每一阶段都需要运动画面、
启停、分辨率变化及拔插恢复证据；编译通过不作为完整驱动适配完成的标准。
