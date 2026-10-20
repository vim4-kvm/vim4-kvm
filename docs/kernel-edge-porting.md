# 7.3 USB 与音视频适配拆解

2026-10-19 对固定 7.3 源码和 common_drivers `563cff9dab2c8cd44590bf57c8ffaa7e2dae35e1`
做静态核对，并对照首次启动日志。结论：USB 缺少 CRG UDC 实现与设备树接入，
也缺 configfs 功能配置；后续已加入实验 CRG 驱动，见下方实现记录。
HDMI 输入和编码需要独立适配，不能靠启用同名驱动解决。
首次基础启动见 [首次启动](bringup/2026-10-19-edge-firstboot.md)，后续 USB 结果见
[CRG 实测](bringup/2026-10-19-crg-udc.md)。下文保留各阶段验证边界。

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

## CRG 实验驱动（2026-10-19）

内核提交 `faa738ca925596cb7772f53895273d5d4ab46b18`，源码在 Linux 工作树
`drivers/usb/gadget/udc/crg/`，已保留厂商版权和既有 EP0 重连修复。
实现与独立测试设备树在此阶段已提交，尚未安装到板子；后续上板结果见本节末尾。

- 清除旧 configfs 私有结构与强制重新绑定接口，使用标准 UDC 注册与用户空间绑定。
- PHY、共享复位和电源域由现有 Meson 父驱动持有；子驱动只持有 core 时钟引用，
  申请互斥 MMIO 资源，并要求 T7 父设备处于 peripheral 模式。
- 单实例、USB high speed；为避免未实现的上下文恢复，绑定时拒绝系统休眠。
- 检查 DMA 分配、控制器复位和 IRQ 申请错误；EP0 状态请求不足时返回 ENOMEM。
  保留 gadget.irq 与异步回调同步，补齐失败回收与 remove。
- 端点停止等待改为有界轮询。释放 DMA ring 前确认 halt 或 reset 成功；
  两者都超时则保留缓冲区并阻止本模块再次 probe，避免硬件继续写入已释放内存。
- pullup 关闭时停止控制器；不再保留旧代码中未启用的 VBUS 线程。

独立 `amlogic-t7-a311d2-khadas-vim4-udc-test.dtb` 将 fdd00000 子节点替换为
`amlogic,t7-crg-udc`，fde00000 仍是 xHCI。父设备设为 peripheral，且不开放角色切换。
普通 VIM4 DTB 的 SHA-256 保持不变，不会自动接管现有 USB host。

验证结果：VM `~/build/kernel-edge-crg` 完整 Image/dtbs/modules 构建成功、无编译警告；
modpost 通过，crg_udc.ko 不再依赖厂商符号。
实际事件分发函数的 EP0 reset/setup/unbind 回归，以及实际初始化函数的
DMA/状态请求分配失败、IRQ defer/申请失败回归通过。测试入口在上述驱动目录 README.md。

产物 SHA-256：

- Image：`2d434f1bb36412b524f0464321f1ddfd3fb9579df17c70b4f73e2ef144ad2b1a`。
- crg_udc.ko：`85dfa44f0db6cf02b7e4664f6551c96f97d7d262d8ddce7b879c1b8e345258db`。
- udc-test DTB：`3ee57f2ea5ad5618c068f0874840c858267f3efee1ef14dcd20ad516a9f673ba`。

日志：`logs/kernel-edge/crg-build.log`、`crg-regressions.log`、`crg-artifacts.log`。
此次输出目录由 gadget 构建目录的 reflink 副本增量构建，已用新构建脚本的报告逻辑
重新生成 build.json，记录本次提交、配置和两种 DTB。最终配置与配方执行
olddefconfig 的结果完全一致。主仓库 83 项离线测试通过、4 项跳过。

下一步先核对 T7 peripheral PHY 路由，再以独立内核 release 和匹配模块试启动，
只验证 UDC probe/卸载与最小 HID 枚举。仍需审查和实测继承的 DMA、请求完成及
断开/复位路径。当前编译结果不能证明 USB 已能使用，也不能作为完整 KVM 内核部署。

后续已完成上述首次上板，发现并修复解绑后状态残留（`9610500b6fee`）；
测试版本、日志和验收范围见 [CRG 实测](bringup/2026-10-19-crg-udc.md)。
后续三轮真实键鼠＋只读存储组合也通过，见 [组合实测](bringup/2026-10-19-crg-composite.md)；
主机主动 reset、休眠、可写介质和 UAC2 等仍需验证。

## HDMI 输入、编码与音频依赖

已完成 T7 接收器电源、功能时钟、TOP 资源与源端 5V 读取，
三轮加载/卸载和旧 debugfs fd 检查通过。后续加入 EDID 校验、RAM 读回和 HPD 请求，
Mac 发送端已精确读回两份不同的 128 字节 EDID 及一份 256 字节 EDID。
后续固定 148.5 MHz PHY 实验路径已扩展至 COR 对齐、1080p60 时序检测及 VDIN
RGB24 完整快照，三处帧号一致且重复采集推进。当前版本与测试边界见
[HDMI 取帧实测](bringup/2026-10-19-hdmirx-frames.md)。

| 功能 | 当前厂商实现入口 | 主要依赖 / 新内核缺口 |
|---|---|---|
| HDMI RX | drivers/media/vin/tvin/hdmirx/ | EDID/DDC、固定 PLL、COR 对齐与 1080p60 已测；仍缺动态 PHY 及标准采集接口；snps_hdmirx 不能直接接入 T7 |
| VDIN | drivers/media/vin/tvin/vdin/ | 已有独占 VPU 的有界 DMA 快照；后续建立共享 VPU 与 V4L2/videobuf2 连续采集 |
| DMA-buf 输出 | drivers/media/vfm_cap/vfm_cap.c | VFM provider/receiver、codec_mm；必须保留缓冲持有和 CPU 同步语义 |
| Wave521 编码 | drivers/media_modules/frame_sink/encoder/multi/vpu_multi.c | codec_mm、canvas、CPU 检测、厂商电源域及 vdec 电源辅助接口，现有 amvenc_multi 用户态 ABI |
| HDMI 输入音频 | sound/soc/amlogic/auge/tdm.c | hdmirx/hdmirx_b 输入源、RX 音频状态、TDM DMA 与路由；输出声卡注册不能证明输入可用 |

7.3 已有 chips-media/wave5 编解码驱动，但 wave5-vpu.c 当前 OF 表仅匹配
ti,j721s2-wave521c。需核实 T7 的寄存器、固件、电源和 DMA 接口后才能决定复用。
若改用标准 V4L2 M2M，还需改现有 amlvenc 用户态接入，不能假定旧 ioctl ABI 可用。

先完成独立 HDMI 输入取帧，再接编码，最后接音频与应用。每一阶段都需要运动画面、
启停、分辨率变化及拔插恢复证据；编译通过不作为完整驱动适配完成的标准。
