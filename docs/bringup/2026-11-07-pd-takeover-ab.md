# 2026-11-07：Linux PD 接管 A/B 与采用边界

**首轮交替计划完成：A 原参数2/10冷复位，B追加 `module_blacklist=fusb302` 为0/10。**
两次自动恢复A和最终自然默认A另列，实际23次Linux启动：A13次/2复位、B10次/0复位。
该差异不足以单独证明PD根因；本次没有物理VBUS观测，失败启动的TCPM末段日志也没有完整留存。
用户随后取消追加15次B，原因是 **“用户决定直接采用、持续观察”**；首轮未追加或重跑样本。
以下首轮结束时仍是正式原参数A；[采用B为正式默认及仓库策略](2026-11-07-pd-firmware-default.md)另行留证。

## 固定条件与入口

内核固定正式fd41fb5：`7.3.1-vim4-20261105`，GNU build ID
`bdbfa439f298e92b5bad092528d11119a974f262`；同一Image、FDT、模块和无线开启状态，
`CONFIG_TYPEC_FUSB302=m`。没有编译内核、改驱动/DT/FIP、saveenv、HID注入或切EDID。
Mac→USB-C功率计→板子拓扑未变，但用户此次不看功率计，没有表显或物理VBUS采样。

两组均从 `sudo reboot` 进入同一次串口打断U-Boot流程，均用
`sysboot mmc 1:1 any ${pxefile_addr_r} …; reset`，未用额外init或RAM模块挂载：

- A读取 `/extlinux/extlinux.conf`；B读取本任务独占的 `/pd-ab-<id>/variant-B.cfg`。
- B文件逐字复制正式配置，只在Mainline的APPEND尾部追加黑名单；`${eth_mac}`等变量原样保留。
- 文件diff只有这一处；运行后B的 `/proc/cmdline` 与同票入场A逐字比较，只多该参数。
- 按B、A交替各10次；每次发BOOT通知，完成稳定uptime≥60秒及检查才进入下一次。
- 冷复位只计量，不主动重试；自动默认恢复单独计数。420秒不能自然恢复或B累计2次复位才停。

首票FIFO1627在B文件创建及任何BOOT/重启前退出：错误地要求含`${eth_mac}`的APPEND模板
直接等于运行时cmdline。入场proof/视频通过，零启动、零板端文件变更；该失败不计样本。
按协调者裁决改为模板仅文本追加、运行后比较cmdline，换FIFO **1628**，50分钟sampling票完成。
连续UART在排空后记录；每次SSH最早可达时与稳定后各采一份dmesg、journal、模块、Type-C、
UDC和服务状态。TCPM标准debugfs `usb/tcpm-1-0022/log`读操作会推进日志环尾，早期/稳定快照分别保留。

## 结果与统计边界

| 口径 | A原参数 | B黑名单 |
|---|---:|---:|
| 计划请求/冷复位 | 10 / **2** | 10 / **0** |
| 原请求直接稳定 | 8 | 10 |
| 自动恢复启动/冷复位 | 2 / 0 | 0 / 0 |
| 最终自然默认恢复/冷复位 | 1 / 0 | 0 / 0 |
| 实际Linux启动/冷复位 | **13 / 2** | **10 / 0** |

20个计划槽位均完成检查；两个失败A的检查是在自动恢复A稳定后完成，不能算原失败启动通过。
10个B均无fusb302模块、无Type-C端口，UDC为configured，SSH/原服务及被动4K视频通过。
每个B的PD服务均打印 `PD bootstrap skipped: controller reserved for kernel TCPM`，没有退回原始I²C
协商；板级gadget日志含keyboard/absolute/relative，One-KVM OTG HID backend初始化成功。
未发送输入，也没有新的Mac侧人工枚举确认。

11个可SSH的A启动（原请求8、自动恢复2、最终默认1）均有实际Soft_Reset AMS启动并随后正常协商；
没有观察到Get_Source_Cap实际AMS或 `Initiating hard-reset`。TCPM中的
`pending … -> HARD_RESET_SEND @60ms`后来被正常响应取消，**不计实际Hard Reset**。
10个B无TCPM端口/日志。两个失败A未在SSH可达前取得TCPM日志，不能把恢复后的日志归到失败启动。

本轮2/10对0/10的双侧Fisher精确检验p=0.473684。按协调者指定的历史粗口径14/75合并A，
得到约16/85对0/10，p≈0.203662；这是不同历史入口/条件的汇总，不是随机同条件样本。
原拟再采15次B已由用户取消；采用B是用户的运行策略决定，不写成已证明PD致因或已解决冷复位。

## BOOT6为什么用了97秒

BOOT6耗时 **97.199秒**，普通单次约80秒。请求后7.7627秒开始第一次Linux，
7.296069秒后返回ROM；第二次Linux起点为请求后25.4962秒，比第一次晚约17.7335秒。
这段自然恢复解释额外耗时，不是单次TCPM协商或SSH等待用了97秒。

第二次ROM的 `T7:BL:` 前缀缺损，幸存 `:CF;RCY:`、`reboot_mode : cold_boot`和第二次Linux。
最初仅查完整T7标记的私有计数将该槽误标false；原始JSON不追改，逐启动总表按完整UART更正为一次复位。
最早成功SSH采证标记为请求后 **38.687685秒**，快照uptime12.77秒，属于第二次自然A；
它是最早实际采证时刻，不是未记录的SSH端口开放时刻。该次恢复的Soft_Reset日志不能证明第一次如何失败。

BOOT14耗时 **96.977秒**，同样在首次A的 **7.180929秒**回到完整T7 ROM标记后自然恢复。
两个失败启动的boot_id由实验完成后的持久kernel journal补证，分别为
`e5b5a9e1359444d3915e3e5779bf7e1a`、`2276c52eb5984882a2d9300a265c22c5`。
持久日志仅留到约4.876/4.858秒，没有fusb302/tcpm或实际hard-reset行，末段未覆盖。
持久日志补采在20个实验请求全部结束后、同票最终恢复期间完成，没有给A/B中途增加不对称采证负载。

BOOT6回ROM前最后15行内核输出如下；该失败片段内无fusb302/tcpm行：

```text
[    3.456849] meson8b-dwmac fdc00000.ethernet: Active PHY interface: GMII/MII (0)
[    3.460948] meson8b-dwmac fdc00000.ethernet: RX Checksum Offload Engine supported
[    3.470712] meson8b-dwmac fdc00000.ethernet: Wake-Up On Lan supported
[    3.480460] meson8b-dwmac fdc00000.ethernet: Enabled RFS Flow TC (entries=10)
[    3.485301] meson8b-dwmac fdc00000.ethernet: Using 32/32 bits DMA host/device width
[    3.489101] EXT4-fs (mmcblk0p2): re-mounted ec07a3f7-a5fb-46fc-b8f6-8f6c347fcae6.
[    3.560548] cfg80211: Loading compiled-in X.509 certificates for regulatory database
[    3.573760] Loaded X.509 cert 'sforshee: 00b28ddf47aef9cea7'
[    3.578829] Loaded X.509 cert 'wens: 61c038651aabdcf94bd0ac7ff06c7248db18c600'
[    3.628479] systemd-journald[162]: Received client request to flush runtime journal.
[    3.682564] systemd-journald[162]: /var/log/journal/027febbd835a437bab6eb0b6db9c7b6a/system.journal: Journal file uses a different sequence number ID, rotating.
[    3.692966] systemd-journald[162]: Rotating system journal.
[    4.362080] brcmfmac: brcmf_fw_alloc_request: using brcm/brcmfmac43752-sdio for chip BCM43752/2
[    4.794439] brcmfmac: brcmf_c_process_txcap_blob: no txcap_blob available (err=-2)
[    4.804367] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43752/2 wl0: Jan 18 2024 14:50:40 version 18.35.387.23.217 (ga18eaaff) FWID 01-e47f9a86
```

BOOT14回ROM前最后15行如下；该失败片段内也无fusb302/tcpm行：

```text
[    3.433091] meson8b-dwmac fdc00000.ethernet: TX Checksum insertion supported
[    3.437991] meson8b-dwmac fdc00000.ethernet: Wake-Up On Lan supported
[    3.442807] meson8b-dwmac fdc00000.ethernet: Enable RX Mitigation via HW Watchdog Timer
[    3.447759] meson8b-dwmac fdc00000.ethernet: Enabled RFS Flow TC (entries=10)
[    3.451501] meson8b-dwmac fdc00000.ethernet: Using 32/32 bits DMA host/device width
[    3.473348] EXT4-fs (mmcblk0p2): re-mounted ec07a3f7-a5fb-46fc-b8f6-8f6c347fcae6.
[    3.520571] cfg80211: Loading compiled-in X.509 certificates for regulatory database
[    3.533941] Loaded X.509 cert 'sforshee: 00b28ddf47aef9cea7'
[    3.538952] Loaded X.509 cert 'wens: 61c038651aabdcf94bd0ac7ff06c7248db18c600'
[    3.618555] systemd-journald[163]: Received client request to flush runtime journal.
[    3.666028] systemd-journald[163]: /var/log/journal/027febbd835a437bab6eb0b6db9c7b6a/system.journal: Journal file uses a different sequence number ID, rotating.
[    3.672141] systemd-journald[163]: Rotating system journal.
[    4.319235] brcmfmac: brcmf_fw_alloc_request: using brcm/brcmfmac43752-sdio for chip BCM43752/2
[    4.771763] brcmfmac: brcmf_c_process_txcap_blob: no txcap_blob available (err=-2)
[    4.777829] brcmfmac: brcmf_c_preinit_dcmds: Firmware: BCM43752/2 wl0: Jan 18 2024 14:50:40 version 18.35.387.23.217 (ga18eaaff) FWID 01-e47f9a86
```

## 首轮恢复与证据

最后一次为不打断U-Boot的正式默认A，零冷复位，85.079秒完成稳定检查。
2372 protected_files逐项相同，默认extlinux SHA未变，临时B文件及专属目录按SHA核对后删除。
最终被动3840×2160 **59.58fps**、帧8→306通过；原服务、SSH及UDC恢复，票已释放。
没有写大包、覆盖历史证据或部署新内核；原始输出均在本工作树忽略目录。

[逐启动CSV](data/2026-11-07-pd-takeover-ab-boots.csv)与[完整摘要](data/2026-11-07-pd-takeover-ab-summary.json)
分别保存23次启动及计划/自动恢复口径。原始UART为 `logs/pd-ab/window-1628/uart.raw`，SHA256
`aa8e9e4a60011d1dc420271c11e9d7549fa7657804b3e43f97f73a3c9dc2dd2a`；同目录有主机时戳分块、
每次早期/稳定快照、模板diff两侧文件、被动视频及完整proof。BOOT6/14持久kernel日志也在该目录。
私有执行/分析脚本在 `build/pd-ab/`。未运行物理VBUS/RESET闭环测量或取消的B补测。
收口前613项主仓测试通过（17跳过），原始输出 `build/pd-ab/record-tests.log`；diff检查干净。
