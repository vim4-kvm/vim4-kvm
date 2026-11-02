# 2026-11-02：BCM43752 厂商扫描请求、驻留与 SDIO 中断对照

使用此前的 5 GHz 保存连接、5.15.137-vim4kvm-hdrdual6/厂商 dhd 和
7.3.0-vim4kvm-uhd6+/brcmfmac。私有证据在 `logs/wifi-vendor-scan/`。
此前扫描顺序实验见[交替对照](2026-11-02-wifi-scan-pairs.md)。

| 观测 | 5.15 实测 | 7.3 实测 |
|---|---|---|
| 首次普通 escan | v2、内层 length 76、26 个信道 | v2、36 个信道；将内层 length 单独设成 76 后仍崩 |
| 未关联主动扫描驻留 | 80 ms | 默认设置 40 ms；改 80 ms 的第八次仍崩 |
| 运行时地区 | CN/0 | US/0；连接的 5200 MHz AP 广播 US |
| 空口休眠参数 | 连接后 pm2_sleep_ret=2000 | 连接后也读回 2000，未激活时曾读回 200 |
| 漫游 | roam_off=1 | roam_off=0 |

5.15 运行 24 次完整激活，全部成功；厂商 dmesg 显示各轮重新启动固件。
96 次普通扫描均为 26 个信道。直接观测 wl_do_escan 在 wldev_iovar_setbuf
调用前的请求，编译产物中亦可见写入 version=2、length=76 的指令。
这是 wl_cfgscan.c 的 wl_scan_prep 使用 sizeof(wl_scan_params_v2_t) 的结果。
7.3 的 brcmf_escan_prep 会将信道数组和 SSID 长度计入内层 length。
只改该字段的 7.3 请求实测 outer=2、inner=76、36 信道、一个 SSID、总长 188；
该轮首次激活即出现 firmware halted。单独改驻留时间的候选由 cmd 187 探针核实
写入 80，前七次成功，第八次出现 firmware halted。
两次故障从发出 escan 到主机报告分别为 0.517 和 0.951 秒，转储分别在
0x180013fc、0x180013fe 报 AXI slave error；延迟差接近 11 个信道各增加 40 ms。

5.15 的 dhd_config.c 给这款芯片默认设 CN/0，7.3 未激活时 cfg80211 全局为
00，固件已为 US/0；读取固件与读取主机监管域是不同的观测。未人为更改国家码。

## 主机异常

临时禁止空闲 watchdog 让 SDIO 睡眠后，七对重载对照均成功，探针证实候选未切换 KSO。
下一对卸载报告模块仍在使用，结束该组。随后切换中断配置时出现一次主机 panic 并自动重启。
pstore 保留了移除路径 brcmf_ops_sdio_remove → brcmf_bus_cancel_reset_work 与异步
brcmf_sdio_firmware_callback 仍在 attach 中使用 rxctl 的栈。此类重载测试存在宿主
生命周期问题；它与连接时固件 TRAP 4 的证据应分别统计。后续中断实验只加载一次，
通过正常重启恢复，未强制卸载。

## GPIOX_7 独立中断

5.15 的 kvim4.dts 在 aml_wifi 节点描述 GPIOX_7，实际 dhd 日志记录
HW_OOB、IRQ 102、flags=0x4。7.3 的 wifi@1 没有中断描述；brcmfmac
因此使用 SDIO 带内中断。T7 pinctrl 的 GPIOX bank 对应 GPIO IRQ 20–39，
GPIOX_7 对应 27。单次加载的诊断模块为该线建立高电平中断映射后，
brcmf_sdiod_intr_register 在 enable_irq_wake 返回 -ENXIO 时终止初始化；
两端 irqchip 的唤醒支持不同。允许此返回值后，实测 /proc/interrupts 出现
meson-gpio-irqchip 27 Level brcmf_oob_intr。实验模块经历一次加载和连续
24 次连接，全部成功，中断计数从 111 到 8149。此处没有测试挂起唤醒。

内核候选分支 `wifi-43752-vim4-hostwake-trial` 的 91e8e8d9274dc 在
无系统唤醒能力时保留普通中断，并关闭 WoWLAN 能力声明；b795e77b5fb43
在 VIM4 设备树声明该 IRQ。模块和 DTB 构建、反编译 IRQ 单元 (27, 4) 及
checkpatch 通过。板上运行的是等效的临时 IRQ 映射及绕开唤醒能力检查的
诊断模块；这两个提交的组合尚未上板，未进入正式分支。

正常重启恢复默认带内中断后，同一保存连接连续 12/12 成功。现有成功序列不足以
确认中断接线与固件 PHY 崩溃的因果关系。板票 484–493 累计约 28.34 分钟。
末尾核对正式模块 build ID da667c427b389418706c4de5107745a46531ac42、
Wi-Fi disabled、默认路由 eth0、四项服务 active、UDC configured，票已释放。
