# 计算、总线、存储与电源

固定 [V/E 证据](sources.md)，回到 [总表与阶段](README.md)。本页 24 项。
“部分”包含实现存在但厂商全范围未验；风险H/M/L，估计为人日，共享依赖不重复相加。

GPU/CPU/PM 后续离线审查固定正式起点 `1d80e6ccc3641`；六个候选提交在
`vim4-platform-pm`，未部署、未提升下表验收状态。见
[电压、DVFS 与 PM 证据](../archive/platform-pm-offline.md)及[批量上板清单与时长](platform-pm-board-checklist.md)。

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| P01 八核SMP、内存、GIC/定时器/基础启动；V2:23–300，V1 memory | 完全对齐 | 限本行基础启动功能，E0/E1八核与约7.69GiB可用，双内核重启回归。[首次启动](../bringup/2026-10-19-edge-firstboot.md)、[M0](../bringup/2026-10-23-display-m0-r4.md)；不包含idle/低功耗 | 保持主线架构；后续版本升级做启动/内存压力回归，1–2 / M / 两板型、串口；非新增缺口 |
| P02 CPU DVFS/调压/芯片分档；V1:2147–2235，V2:477–1228 | 部分对齐 | 两簇四bin、T7/T7C共184个频压条目与7.3逐项一致；标准OPP/PWM和按簇secure bin已接。默认governor与温控策略有差异，全部批次稳定性未验。[对照](../archive/platform-pm-offline.md#cputhermal-与风扇对照) | 保持主线cpufreq/OPP/regulator；验证升压先于升频和各bin/温区，6–12 / H / 两芯片批次、可测电压与负载/散热；不试表外电压 |
| P03 GPU OpenGL/渲染、devfreq；V2 GPU，V8 | 部分对齐 | Panfrost与250/400/500/666/800MHz纯调频通过，但旧Mali专有用户态功能/全部API未齐。[GPU](../bringup/2026-10-21-edge-gpu-devfreq.md)，E0:109 | 主线DRM/Panfrost＋Mesa，配D01/D02作GBM/compositor/压力及API覆盖；5–10 / M / HDMI sink、渲染测试、GPU压力 |
| P04 GPU逐频调压；V2o:4744，V8 | 部分对齐 | **保持启动PWM电压**；追查厂商Linux、U-Boot PWM编码、GPU leakage/corner及签名BL31后仍无可信逐频电压表；已检查的厂商Linux路径只切频，未添加opp-microvolt。[本轮结论](../archive/platform-pm-offline.md#gpu-电压结论) | 保留主线OPP/devfreq/regulator；先取得T7板型/分档电压表和PWM实测标定，3–7＋等待 / H / 万用表/示波器、GPU负载、温控；禁止表外电压，不据闭源固件缺源码断言其绝不调压 |
| P05 NPU推理与驱动；V0→V2o四NNA wrapper，V1→V2:386 ADLA，V7 | 缺失 | kvim4n实际加载adla_core，不能把Vivante AMLOGIC_NPU/Galcore当其驱动。E仅有NNA电源域/供电命名，无推理链 | 外围先厂商移植后整理；分清T7/T7C IP，先可控DMA/IOCTL/PM和匹配SDK验证，再评估accel/DRM通用接口；12–25起 / H / 对应板型、可合法使用的SDK和模型、参考CPU结果；Q07依赖 |
| P06 genpd/runtime PM、时钟/复位、低功耗；V2:380,CCF，V2o thermal | 部分对齐 | VPU/VI、USB/SDIO/eMMC临时常开保留，SRAM/DDR/NOC等固件必需常开另列；Wave runtime恢复不等于live instance系统恢复。[逐消费者审查](../archive/platform-pm-offline.md#系统挂起与唤醒缺口) | 主线genpd/CCF/reset生命周期，逐消费者证明保存/重建再解除临时常开；D01/R02/E03/U04先就绪；10–20 / H / 功率计、串口、独立复位、同板厂商基准 |
| P07 六温区/安静自动风扇；V2o:2890–2975，V1:1575，V 主内核khadas-mcu | 完全对齐 | 限已实现风扇调速、最高有效温度策略、故障保底；7.x标准thermal cooling已验，主动安静曲线替代旧策略，不减调速能力。[风扇](../bringup/2026-10-20-edge-quiet-fan.md)，M0回归 | 保持thermal/hwmon实现，其他温区/芯片批次回归1–3 / M / 原装风扇、温度与转速外测；系统恢复另见P08 |
| P08 整机挂起/恢复、cpuidle；V2:220,302 PM，V1:2155 | 部分对齐 | 候选补标准PSCI CPU idle、风扇回滚/恢复和Panfrost OPP错误传播，RX/VDIN/T7 Wave在prepare显式拒绝；CRG/handoff仍拒绝。Meson watchdog在suspend停计数，30s运行时保护不能保证deep复位。[离线证据](../archive/platform-pm-offline.md) | 核心主线PM/genpd/ASoC/DRM，先DMA quiesce/context恢复、唤醒及独立复位，再逐域/整机；P06、E03、A01、U04；20–40 / H / 串口、功率计、独立RESET；真正挂起仅列[后续计划](platform-pm-board-checklist.md#批量窗口-b设备-pm-与整机-s2idledeep暂不可执行) |
| P09 唤醒源：IR/Power/RTC/WoL/USB；V2 PM/mailbox/CEC，V1 keys/RTC | 缺失 | HYM8563无DT IRQ；meson-vrtc有AO超时写入契约、未证BL31唤醒；Power轮询、IR关解码器且无IRQ wake；Ethernet/USB路由未验。[唤醒矩阵](../archive/platform-pm-offline.md#系统挂起与唤醒缺口) | 主线IRQ/wakeup与固件协议，先确认RTC/AO路径，再IR/WoL/USB逐项；P08、T02/T03/T05；8–15 / H / RTC备电、遥控器、以太网/USB主机、独立复位；Wi-Fi另协调 |
| P10 CPU/GPU/DDR thermal降频与整机散热；V2o:thermal/meson-cooldev，C thermal | 部分对齐 | 候选补GPU 95°C passive→devfreq cooling；CPU 85/95/110°C比厂商95/105/115°C保守，保留保护；风扇曲线不改。私有hotplug/core/DDR cooling与功耗性能仍欠验。[对照](../archive/platform-pm-offline.md#cputhermal-与风扇对照) | 主线thermal/OPP/devfreq/cooling，按实际功率/温升/吞吐验收；P02/P04/P06，5–10 / H / 可控热负载、热电偶、原装散热器/风扇 |
| U01 USB host2/3、PHY/hub；V1:1398–1440 | 部分对齐 | E1 xHCI/PHY、保留另一host；未完成所有端口速率、热插拔/错误与resume矩阵。[首次启动](../bringup/2026-10-19-edge-firstboot.md)，E6临时常开 | 外围可厂商PHY序列移植后整理，保持USB HCD/PHY/reset/PM框架；P06/U04；4–8 / M / USB2/3盘、hub、键鼠、带宽测试主机 |
| U02 gadget HID/虚拟介质、配置生命周期；V1:1390，C usb/crg | 完全对齐 | 限已验三HID/消费者键与只读/可写虚拟盘、host eject、fd/重绑边界；E6标准UDC/configfs。[USB](../bringup/2026-10-21-edge-usb-functions.md)、[后续盘回归](../bringup/2026-10-22-p2-usb-audio.md)。UAC/网卡/睡眠另列 | 保持标准gadget/function；新增主机矩阵2–4 / M / Mac/Windows/Linux USB主机；非全部组合无限兼容的承诺 |
| U03 UAC2、NCM/ECM/RNDIS/ACM组合；同U02，通用gadget框架 | 部分对齐 | NCM/ECM双向已过；UAC2仅枚举，真实录音受权限阻断；Windows RNDIS缺MS OS描述符/真实传输；ACM未启用。[USB复核](../bringup/2026-10-22-p2-usb-audio.md)。5 IN端点是硬件预算不是软件bug | 标准gadget函数/描述符/应用预算；2–6 / M / 已授权录音Mac、Windows、Linux；不能靠隐藏HID冒充所有功能共存，ACM先确认真实消费者 |
| U04 gadget/host运行中角色、系统PM与remote wake；V1:1408 DRD | 部分对齐 | E专用DT固定peripheral，运行角色切换未接；CRG suspend拒绝，不能移除保护冒充恢复。[适配](../archive/kernel-edge-porting.md)，E6 | 外围CRG厂商序列先移植后收敛USB role-switch、PHY/runtime/system PM；U05/P06、端点DMA停止证明；10–20 / H / DRP主机、可测VBUS、串口、现场RESET |
| U05 PD/Type-C协商与交接；板上FUSB302，V1 I²C/CRG，B | 部分对齐 | 用户态有限协商＋U-Boot合同交接；不是完整TCPM，热重启可能保留历史合同，固定Request/KASLR候选曾早期失败。[PD](../usb-pd.md)、[SD恢复](../bringup/2026-10-22-uboot-sd-recovery.md) | 外围先保留可验证厂商/现有协议，正式USB Type-C/TCPM/role-switch明确一个协议所有者及boot handoff；U04/P06，10–20 / H / PD分析仪、双电源/DRP、microSD回退和人在场；当前禁刷U-Boot |
| N01 PCIe/NVMe、DMA保护窗口；V1:1444，V2:1969 | 部分对齐 | E0:704/E1:493有DWC PCIe+restricted pool/SMC；厂商旧启动无NVMe时也有-110。无本轮实际端点吞吐/错误/PM验收。[首次Ubuntu](../bringup/2026-10-12-initial-serial-oowow-ubuntu.md) | 外围厂商PHY/SMC移植后整理PCI host/DMA API；P06/Q01、保护窗口固件；5–10 / H / M.2 NVMe/适配板、PCIe端点、串口 |
| N02 有线Ethernet/PHY/MDIO；V1:1672–1691 | 部分对齐 | E0网口已用于SSH/传输；TSO/校验和/PTP/WoL、断线与系统PM未全覆盖，不能以SSH可达判全功能 | 标准stmmac/phylib/ethtool；P06/P09，3–6 / M / 千兆交换机、另一主机、时间戳/PTP设备（如需） |
| N03 Wi-Fi/SDIO、WPA3/P2P；V1:1596,2098 | 部分对齐 | brcmfmac/BCM43752与SAE适配已接；固件曾崩溃，真实P2P对端传输未验。[Wi-Fi](../bringup/2026-10-20-edge-wifi.md)、[P2P](../bringup/2026-10-21-edge-wifi-p2p.md) | 外围固件/厂商协议先移植后整理cfg80211/mac80211；保留转储取证。5–10＋固件等待 / H / 专用AP、P2P真实对端、两频段干扰环境；本轮禁止碰Wi-Fi/P2P |
| N04 Bluetooth UART/电源/音频；V1:2104,2125 | 部分对齐 | E0:893有蓝牙serdev；历史bnep/驱动加载不是扫描、配对、ACL/SCO音频验收 | 标准Bluetooth serdev/HCI、rfkill，厂商patchram后端可先保留；A04/UART/32k供电；4–8 / M / BT键盘、耳机、双向传输对端；不变更共享Wi-Fi状态 |
| S01 eMMC HS200/HS400/CQE、可靠写与PM；V1:1647 | 部分对齐 | E启动HS200、1MiB fsync/hash过；不代表厂商HS400/CQHCI/tuning/掉电可靠写全部通过。[启动](../bringup/2026-10-19-edge-firstboot.md) | 标准MMC/CQHCI/pinctrl；先厂商支持范围再速度/压力/重启，P06；4–8 / H / 可恢复测试盘/镜像、串口；不能在根盘做破坏性测试 |
| S02 microSD 热插拔/模式/启动；V1:1623 | 部分对齐 | E0 SD节点已有，但无本轮卡型/热拔插/速率矩阵；厂商树支持不等于当前卡已验 | 标准MMC/regulator/pwrseq；P06、2–5 / M / 多品牌SD/SDHC/SDXC、microSD恢复介质 |
| S03 SPI NOR与eMMC引脚复用 | 部分对齐 | V1:1736、V0:1661均disabled；E0:770也保留disabled。B3..7与8bit eMMC共用，非当前启用能力。[NOR审查](../bringup/2026-10-21-edge-ir-keys-spinor.md) | 选装标准MTD/spi-nor；先安全独立启动与pinmux，不抢根盘，3–6 / H / SD/USB独立启动、NOR夹具；当前禁刷引导区 |
| S04 CMA/dma-heap/codec内存与跨设备同步；V1:133–275,308，V2:codec_io | 部分对齐 | E有512MiB CMA/直接DMA与孤儿缓冲修复，但ION/UVM安全堆/多媒体争用能力未齐；不兼容私有内存ABI。[回收](../bringup/2026-10-20-edge-dynamic-modes.md) | 核心标准dma-buf/dma-heap/vb2/fences；D01/R02/E03/C01、内存和共享带宽预算；8–15 / H / 并行显示/采集/编码/解码与可现场恢复的压力环境 |
| S05 DDR带宽/DMC监控、内存QoS；V2:ddr_bandwidth/dmc_monitor，V1:83 | 缺失 | E无已验T7等效监控接口；CMA空闲不证明总线带宽裕量，常开域不等价于QoS | 外围厂商监控先移植后整理devfreq-event/perf/debugfs；硬件QoS写入归一资源所有者，与D01/R02共享表；5–10 / H / 固定负载、功耗/温度观测、串口 |
