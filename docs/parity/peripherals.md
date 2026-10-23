# 外设与固件辅助功能

固定 [V/E 来源](sources.md)，[总表](../vendor-parity.md)。本页 16 项。
外围允许先移植厂商实现，再整理到标准接口。已用的总线不代表所有扩展引脚、时序和PM均验收。
风险H/M/L；估计单位人日，不包含购买/人工接线等待。

| ID / 厂商能力及来源 | 7.3 状态 | 差异与证据 | 路线、依赖 / 人日 / 风险 / 验证硬件 |
|---|---|---|---|
| T01 IR接收/Khadas键表；V1:2070覆盖前disabled | 部分对齐 | E0启meson-ir/rc-khadas与自动加载，AO唤醒不在此行；真实遥控全键/重复码/抗干扰仍需补。[IR](../bringup/2026-10-21-edge-ir-autoload.md) | 标准rc-core，保留厂商协议/键值映射，1–3 / L / Khadas遥控器、逻辑分析仪、两协议对照 |
| T02 IR发射；V1:2121，V2o:3184 | 缺失 | 厂商irblaster enabled/模块已加载；E无本板已接通发射功能验收，IR接收成功不代表发射 | 外围厂商时序先移植后整理rc-core TX，PWM/clock/载波占空比；3–6 / M / 发射二极管/扩展板、示波器、独立接收器 |
| T03 Power/Function按键；V1:936–958 | 部分对齐 | E0 polled GPIO/adc-keys已注册，ADC channel2开机曾超时，未验物理按键全行为/唤醒。[按键](../bringup/2026-10-21-edge-ir-keys-spinor.md)、[ADC审计](../bringup/2026-10-22-saradc-timeout-audit.md) | 标准input/gpio-keys/adc-keys，先修SARADC独占/握手、再物理长短按与去抖；T06/P09，2–5 / M / 人在板边按键、示波器/串口 |
| T04 LED/PWM LED；V1:961，C amlogic_led | 部分对齐 | E0有pwm-leds heartbeat，未证明厂商state-led/AO固件状态、全部亮度/触发与恢复一致 | 标准LED class/triggers/PWM，先查实际板载LED而非模块全集，1–3 / L / VIM4、目视/光电探头 |
| T05 MCU电源/复位/WoL/USB-PCIe切换；V1:1575，V主内核khadas-mcu.c:838,875–877 | 部分对齐 | 7.x `khadas_mcu_fan`已覆盖风扇；旧驱动额外sysfs控制不等于已被移植，不能由I²C probe推断有安全poweroff/restart | 外围MCU协议先移植后整理MFD/sys-off/reset/供电与mux归属；P09/N01/U01，4–8 / H / 对应MCU固件、双供电、串口/在场RESET；本轮不写命令 |
| T06 SARADC及通用模拟输入；V1:1668，V2:1230 | 部分对齐 | E0启SARADC；开机Function通道2有超时，离线候选不是已部署修复。[审计](../bringup/2026-10-22-saradc-timeout-audit.md) | 标准IIO/ADC arbiter、T7固件所有权和采样时序；不靠关按键消日志；3–6 / H / 已知电压源/万用表、串口、物理按键 |
| T07 HYM8563 RTC与AO VRTC；V1:1569,2241 | 部分对齐 | E0:674有HYM8563，E1:470有VRTC；厂商VRTC最终disabled。读时间/备电保持/闹钟IRQ/深睡唤醒未全验 | 标准RTC，核对备电/IRQ/AO路由；P09，2–5 / M / RTC电池、可控断电和在场恢复；不主动做系统挂起 |
| T08 PWM各bank、供电/32k/风扇外用途；V1:2111–2145 | 部分对齐 | E0 PWM/regulator/wifi32k已用，未逐bank验频率、极性、duty与pinctrl；不能用GPU电压负载试错 | 标准PWM/regulator/clock，厂商T7分频特例可先移植；P02/P04，2–5 / H / 示波器、无负载夹具；不动活跃供电PWM |
| T09 I²C0/1/2/3/5/AO与扩展；V1:1451–1594 | 部分对齐 | 厂商1/2/3/AO enabled，0/5 disabled；E实际用AO等控制器，未完整接通/验外部总线与恢复 | 标准i2c adapter/pinctrl、厂商分频/恢复后端；T05/T07及扩展板，2–4 / M / I²C EEPROM/传感器、逻辑分析仪；不在活跃板做全地址扫描 |
| T10 SPI/SPICC master/slave；V1:1743–1768，V2o:1384–1473 | 缺失 | 厂商SPICC0/2/3均disabled，3下NOR子okay不覆盖父disabled；全局SPI开关不能当实际端口可用。E无本板扩展SPI验收 | 选装标准SPI/spidev或真实设备驱动；先安全pinmux/电源域，3–6 / M / SPI loopback/外设夹具；slave能力需另核对T7实现，不计当前必须追平 |
| T11 UART控制台/BT/扩展口；V1:1693,2125,2131 | 部分对齐 | E控制台与BT节点存在；厂商A/C enabled、E disabled。RS485/流控/各引脚/高波特率未全验 | 标准serial/serdev；厂商FIFO/时钟特例可移植后整理，N04；2–5 / M / UART loopback/逻辑分析仪；不占唯一恢复串口 |
| T12 GPIO/pinctrl/IRQ与gpiomem；V1:782，V2:pinctrl/gpio_intc | 部分对齐 | E标准gpiochip/引脚与IRQ框架已用；未逐bank验IRQ/唤醒；厂商gpiomem不承诺兼容 | 标准gpiolib character device/pinctrl/irqchip，按实际扩展用途补测试；2–5 / M / 扩展IO夹具/逻辑分析仪；禁止碰根盘/供电/PD等活跃引脚 |
| T13 Watchdog、重启、关机；V1:2155,2160，V2:aml_reboot/wdt | 部分对齐 | E正常重启与watchdog驱动存在不证明真实硬件超时/关机供电切断，MCU与PSCI/固件各有边界 | 标准watchdog/restart/sys-off，厂商原因码/MCU后端先移植；T05/P08/Q09，3–6 / H / 串口、在场RESET/电源控制；本轮不触发超时 |
| T14 KXTJ3加速度计；V1:1584–1593 | 缺失 | 厂商I²C节点enabled，但E0未接等效传感器/中断验收；不能从模块未列出推断硬件不存在 | 外围厂商配置移植后整理IIO（先核对已有通用KXCJK兼容性）；2–4 / L / 对应板型、姿态/振动夹具 |
| T15 FT5336/GT9xx触摸；V1:1518–1553 | 缺失 | 厂商两种候选节点均okay不代表两颗触摸同时接板；E配置TOUCHSCREEN关闭，无板级验收 | 外围厂商面板配置移植后整理标准input/I²C触摸驱动，I01面板/引脚；3–6 / M / 对应MIPI屏/触摸扩展板、实际中断连线 |
| T16 mailbox/AO/FreeRTOS/BL40辅助核；V2:mbox_fifo/mbox_devfs，C .config FREERTOS_T7 | 部分对齐 | E的SMC/genpd承担部分服务，无厂商mbox-devfs/FreeRTOS控制的完整等效；bl40_module已加载不证明所有服务有用户 | 外围厂商协议先移植后整理mailbox/remoteproc/rpmsg、sys-off/wakeup；A15/P09/Q01，8–15 / H / 匹配AO/DSP固件/协议、串口、可恢复板；无需为无消费者的私有devfs造兼容层 |

未启用的 w1-gpio（V1:534）不列实际能力；将来真接单总线设备可用标准w1，1–2人日、
低风险、需对应传感器。DVB/tuner/demux/smartcard/CI即便模块已加载，V1:815–909板节点
disabled且本板无已确认外接前端，当前不做；需实际前端后再按DVB框架独立估算。
这两类只作范围说明，不进入能力状态计数。
