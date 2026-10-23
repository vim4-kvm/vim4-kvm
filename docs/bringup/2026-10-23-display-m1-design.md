# 2026-10-23：T7 DRM M1 共存接管设计

目标是 HDMI-OUT 与 HDMI 输入采集同时工作，并保留 HDMI 音频和输入直出路线。
M1 只接管固件留下的 1080p60 RGB888 OSD1：原子提交、GEM DMA、真实显示中断与
地址翻转；不进入现有 meson 全局初始化。实施状态与实测边界见
[M1 记录](2026-10-23-display-m1.md)。厂商寄存器依据及固定源码身份见
[硬件明细](2026-10-23-display-hardware-audit.md)。

## 从 handoff 收敛到完整 meson-drm

7.3 已导入 T7 相关分支和独立 hdmitx21，但原 bind 会全写仲裁、初始化 VPP/VIU、
申请 canvas、建立 VD overlay，并让 encoder/bridge 重配时钟和 PHY。这条路径不能
直接与目前 VDIN 并用。M1 在 `drivers/gpu/drm/meson/` 内增加独立实验入口
`meson_t7_handoff.c`，使用常规 DRM atomic/plane/CRTC/encoder 和 GEM DMA helpers，
复用 hdmitx21 的只读 bridge；不使用 simple display pipe 或复制厂商显示框架。

这是暂时隔离初始化副作用的入口，不是第二套完整 modesetting 驱动。后续把资源
所有权和无副作用的 OSD 操作收敛进 meson-drm，再删除 handoff 专用入口；没有证据前
不把 T7 当作 G12A，仅增加 compatible 后运行旧初始化。

| 硬件层 | T7 与 G12A 路径的差异 / M1 处理 |
|---|---|
| VPU | CLKCTRL、ANACTRL、PWRCTRL、SYSCTRL 分开；M1 不映射这些控制块，不写全局仲裁或 reset |
| VIU / OSD | T7 OSD1 线性地址在 word 0x1a14，单位16字节；stride 在0x1a15，单位16字节。M1 保持已验证的1920×1080、stride5760、RGB888，仅换地址 |
| VPP / scaler | OSD1 scaler 在0x5a00；postblend源编号含VD3。M1保持固件scaler/blend/matrix，不运行G12A初始化或调PQ/HDR |
| VENC | 已部署固件使用ENC2，寄存器word加0x800；M1只读ENCP状态，使用VIU1 edge IRQ，不写VENC中断控制、时序或CONF_ENC_IDX SMC |
| TX | 独立TOP32位/COR8位，不是dw-hdmi。handoff bridge沿厂商0x82000018读ABI查TOP状态、active、TPI_SC；不执行普通bridge的attach/enable初始化 |
| PHY | ANACTRL专用TMDS档位、bandgap和reset序列；M1不映射、不重置、不写PHY |
| 时钟 / 电源 | 持有VPU_INTR、VPU、VAPB、TX_APB、HDMI_PLL引用和VPU_HDMI/VI_CLK1/VI_CLK2域；候选使用只读PLL provider，不set_rate、改parent、关共享域或重编PLL |

厂商参考：`common_drivers/drivers/media/osd/osd_hw.c` 的T7寄存器表、线性MIF和
vsync更新；`drivers/drm/vpu-hw/meson_vpu_osd_mif.c`；
`drivers/media/vout/hdmitx21/hw/{reg_ops.c,hw_t7.c,hw_clk.c,enc_cfg_hw.c}`；
`drivers/power/sec_power_domain.c`。RGB内存布局另与已部署U-Boot的
`drivers/amlogic/media/osd/{osd_fb.c,osd_hw.c}`及M0真实色条证据核对；不修改其格式位。
TX SMC读不能证明所有固件版本兼容；固定已部署pd-handoff固件，不刷引导区。

另一个初始化边界在 `drivers/clk/meson/t7-pll.c`：普通HDMI DCO的 `.init` 会写
init_regs，`.enable` 在未锁定时会复位。M1专用 `amlogic,t7-hdmi-pll-ro` provider
复用同一寄存器描述，DCO使用 `meson_clk_pll_ro_ops`，两个divider使用
`clk_regmap_divider_ro_ops`。注册只做regmap关联，没有PLL init序列；没有set_rate、
enable、disable写回调，divider也不向父级传播改频。普通DT仍选原可写provider。
这使“没有主动set_rate”落实为整个PLL provider生命周期只读，而非依赖锁定状态推测。

TX默认pinctrl由设备核心在bridge probe前应用。候选DT删除 `pinctrl-0/pinctrl-names`，
保留固件HPD/DDC引脚路由；仅检查bridge回调没有写操作并不足以证明启动无pinmux副作用。

## VDIN 共存与资源边界

当前VDIN驱动只读写自身0x1200段、两个仲裁word、一个reset word及0x410b段。
候选DT给原 `vdin_test` 增加 `amlogic,split-vcbus`，保留原平台名、sysfs/debugfs路径
和时钟/电源配置。DT的reg仍描述完整VCBUS；驱动在此profile下只申请、映射下表四段，
访问器拒绝表外word。默认profile仍独占完整窗口，避免旧DT意外允许native显示。
没有取消资源申请后让双方自由写，也没有给全窗创建不受控的第二份映射。

| 消费者 | 实际申请的物理范围（起点 / 长度） | 写入责任 |
|---|---|---|
| VDIN | ff004800 / 400 | VDIN0、matrix、scaler、HDR2、线性写DMA |
| VDIN | ff009c80 / 4 | VPU_SW_RESET，仅更新bit26；显示禁止访问 |
| VDIN | ff009e88 / 8 | word27a2 bit16、27a3 bit0；显示禁止访问 |
| VDIN | ff01042c / c | VDIN double-write、top控制 |
| M1 | ff006840 / 80 | OSD1；只写word1a14的扫描地址 |
| M1 | ff008db8 / 108 | ENC2状态，只读；不使用旧ENC0 INTCTRL/INTFLAG |
| hdmitx21 | fe300000 / 10000、fe380000 / 10000 | 保留资源所有权；handoff仅SMC读TOP/COR，无写操作 |

寄存器word转byte只乘一次4；TX TOP/COR使用byte地址。VDIN0完成IRQ为SPI213，
显示VIU1为SPI197；厂商T7 DRM/OSD handler不读写VENC中断寄存器，M1同样不确认或重配。
probe要求100ms内收到至少两次固件VIU1 IRQ才注册DRM，不自行改mux或开旧ENCP中断。
不复用VDIN IRQ、线程、buffer队列或源端lease。显示没有canvas分配、
AFBC/RDMA写表、VPP复位或仲裁RMW，因此M1两个消费者没有共同写入的寄存器。
这份分段表只覆盖当前VDIN实现；新增采集寄存器时必须重新审查并扩展资源合同。

完整meson初始化前仍需统一VCBUS资源所有者，并给共享仲裁寄存器提供同一把锁下的
`regmap_update_bits`或等效接口。显示只能改自己读master的位，VDIN只能改自己的
写master/request位；不能再全写0x27a2/27a3。VPP视频层的AFBC、HDR/PQ、canvas
与VDIN HDR2不是可以凭名字认作同一实例的模块，必须逐项核对地址、reset和memory-PD。
普通线性M1不使用canvas/AFBC；后续需要时复用统一canvas allocator、按实例分配AFBC，
不能引入厂商独立索引池或G12A AFBC reset。当前T7没有启用该reset操作。

共享时钟由各消费者持引用；显示不降低VDIN所需的VPU/VAPB/CLKB频率。
本阶段维持固件配置，不提供runtime suspend或系统休眠；PM回调拒绝系统挂起。
完整驱动需要按活跃读/写客户端投票决定最低频率、管理显示专用gate，并覆盖blank、
采集启停和模式切换，不能让关闭显示关掉采集依赖的域。ENC0/ENC2像素分频的CCF建模仍有缺口。

## 固定接管合同与缓冲生命周期

专用display-m1 DT继承M0双帧no-map保留区，禁用simple-framebuffer及原native VPU。
驱动拒绝仍启用simple-framebuffer的DT，检查reserved-memory、OSD线性使能、地址、
RGB888格式位、stride、窗口及ENC2 ENCP 2200×1125总计数；bridge检查1920×1080
active。任一不符拒绝probe，不尝试修正PLL、时序、scaler或TX。不支持任意U-Boot环境、
MIPI、4K输出handoff、59.94与60的自动识别；60Hz来自匹配固件合同，不能从计数推算实时时钟。

固定sink在DRM中报告connected，不实现物理HPD。厂商T7从GPIOW15读HPD，不能把
TOP_STAT0位0当HPD；M1不为读取它改GPIO/pinmux。真实HPD与EDID属于后续里程碑。

只公布一个primary plane、一个CRTC及固定模式，格式为 `DRM_FORMAT_RGB888`（RG24）；
要求完整1920×1080、pitch5760、offset0、linear、16字节地址对齐及32位DMA边界。
GEM分配、PRIME和隐式输入fence使用标准helpers，暂不开放缩放、裁剪、旋转、YUV/AFBC。
modetest必须显式选择RG24，不能把默认32bpp缓冲当作固件的24bpp格式。

atomic提交工作线程发布地址请求，IRQ在vsync写地址，再等下一次真实IRQ后才完成事件、
释放旧scanout引用；没有软件定时器伪造vblank。100ms超时标记fault，保留旧帧和待翻转帧
引用直到重启，拒绝新提交，日志明确说明故障。延迟到达的IRQ不会释放这两份引用。
关闭CRTC/移除plane时切回保留的固件帧；这是实验接管的返回行为，尚非完整DPMS消隐。
内建配置禁止模块卸载和sysfs解绑，避免固件扫描状态与GEM释放生命周期分离。
两次IRQ退休是保守策略，实际翻页频率另行记录；1080p60输出时序不代表每秒完成60次flip。

一帧RGB888为6.22MB；两张测试缓冲约11.87MiB，另有已保留12MiB固件区。
固定模式、stride不变时，扫描有效读取量与M0相同（约0.373GB/s，仅像素载荷算术值）。
新增GEM仍占全局CMA；必须用实际4K60双编码与音频/HID回归检验内存、总线及中断影响，
不能用资源无交集推导性能与长期稳定性通过。

## HDMI 音频与输入直出接口

HDMI音频是后续必需能力。M1 handoff bridge不注册HDMI音频ops，不改现有
VIM4HDMIRX/TODDR_A声卡，不宣称已有输出。后续复用独立hdmitx21 bridge的标准
HDMI codec接口，建立独立FRDDR→TDM/I²S→TOHDMITX→TX AIP/ACR/packet播放链。
为输出单独建声卡，保持输入名称与路由；先验证48k双声道PCM，再验证44.1k、mute、
热插拔和模式变化。核对MCLK/2、N/CTS、音频PLL及mux，不重设RX/TODDR正在用的源。
必须同时采集RX并测TX声音，不能用网页收到输入音频代替HDMI-OUT音频验收。

直通采用VDIN完成帧→DMA-buf→DRM PRIME→显示plane的标准接口，不使用用户态
memcpy或把仍在写入的DMA槽直接交给OSD。未来增加支持NV12等格式的VD层/转换路径；
M1的RGB888 plane不能显示当前KVM默认的NV12/NV21缓冲。导入时检查物理连续性、stride、
modifier、DMA范围和色彩编码，支持不了则明确拒绝，不能静默复制后称为零拷贝。

当前direct-DMA导出缓冲的lease与队列重用仍需加入显示消费者：VDIN完成后才交给显示，
显示切离旧帧后才归还生产者；用dma_resv输入fence及scanout/out-fence或显式lease
管理所有权。fence等待放提交工作线程，不放IRQ；流重建、STREAMOFF、热插拔与孤儿缓冲
必须保留引用，直到DMA与扫描都停止。用户态可先通过标准DRM/V4L2验证格式和所有权，
再决定内核接口，不预先添加未实现的私有ioctl或虚假音频/直通能力位。

VDIN完成帧与输出vblank属于独立时钟域；按输出节拍选择最新完整帧、统计丢弃/重复与
队列深度，不能承诺输入输出相锁或零帧延迟。桌面OSD与直出VD层的blend/z-order后续
分别验收；编码器和显示器同时持帧时，缓冲数量、背压及CMA预算必须覆盖两个消费者。
