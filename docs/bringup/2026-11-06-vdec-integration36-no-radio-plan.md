# 2026-11-06：integration36 无线初始化屏蔽变体计划

**仅离线准备，未排板、未启动变体、未部署，待协调者批准。**
[r78](2026-11-06-vdec-r78-full-stop.md)两次候选冷复位已停止整个全集系列；
本计划不沿用其剩余板票授权。.36累计6次Linux启动/4次冷复位，正式eMMC至少41次/8次。
唯一USB-C连接Mac，同时供电和HID；无线固件加载附近出现复位，峰值供电不足仅是假设，
没有VBUS/电流/RESET测量，不能据末条日志归因。

## 选择及证据

只给同一.36 RAM候选的extlinux APPEND追加三项，不修改正式默认、rootfs配置、
Image、模块、DTB或init，不执行saveenv：

```text
module_blacklist=brcmfmac,hci_uart,btbcm
initcall_blacklist=mmc_pwrseq_simple_driver_init
systemd.mask=bluetooth.service
```

核对对象是源码`943198734a1c803d780af845a49ed04fa2e933d6`及实际封包config、
modules.dep、modules.builtin、DTB、同次构建System.map，不用当前主线替代候选身份。
原始摘录保存在`build/hwdecode-parity/integration36-no-radio/`的
`source-audit.json`、`module-audit.json`、`native-aliases.log`。

| 路径 | 实际.36配置与加载方式 | 屏蔽理由 |
|---|---|---|
| Wi-Fi | BRCMFMAC=m、BRCMUTIL=m；SDIO modalias经udev/kmod加载brcmfmac，其wcc/bca/cyw扩展依赖它 | 内核module_blacklist也拒绝显式插入，不仅依赖modprobe别名规则 |
| Bluetooth | BT=m、BT_HCIUART=m、BT_BCM=m；HCIUART_SERDEV=y和HCIUART_BCM=y编入hci_uart模块；uart_c子节点brcm,bcm43438-bt匹配hci_uart | 阻止serdev probe/HCI setup/固件下载；btbcm同时屏蔽 |
| SDIO上电 | MMC_MESON_GX=y、PWRSEQ_SIMPLE=y、COMMON_CLK_PWM=y、PWM_MESON=y | 仅禁brcmfmac仍会执行MMC枚举和pwrseq，因此跳过单个内建provider注册 |
| 用户态 | 原候选已mask bluetooth-khadas.service、rc-local.service；r77仍见bluetooth.service和hci0固件日志 | 新增bluetooth.service临时mask；保留NetworkManager和SSH |

`kernel/module/main.c:2933–2953,3400–3412`实施内核插入黑名单；
`init/main.c:1220–1286`在CONFIG_KALLSYMS=y时按函数名匹配initcall黑名单。
System.map确有`mmc_pwrseq_simple_driver_init`，不同于eMMC provider的
`mmc_pwrseq_emmc_driver_init`，后者不屏蔽。

`drivers/mmc/host/meson-gx-mmc.c:1297`在reset及mmc_add_host之前调用mmc_of_parse；
`drivers/mmc/core/host.c:424`转mmc_pwrseq_alloc，`core/pwrseq.c:21–50`在DT指定
provider尚未注册时返回-EPROBE_DEFER。`core/pwrseq_simple.c:60–92`才执行外部时钟
使能和reset释放。因此预期SDIO host停在deferred probe，不运行无线枚举/上电序列。
这不是禁用整个MMC/PWM驱动；eMMC根分区和SD卡路径保留。

实际DTB只有一个mmc-pwrseq属性，消费者为sd_emmc_a。候选DTS
`arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4.dts:148–155,316–321,1432–1469`
对应GPIOX_6、wifi32k和SDIO；`:1683–1703`为uart_c Bluetooth、GPIOX_17 shutdown及
同一wifi32k。`drivers/bluetooth/hci_bcm.c:1506–1543`的serdev probe和后续open/setup
控制电源、下载固件。屏蔽hci_uart阻断此路径。

当前rootfs的全部modules-load.d/modprobe.d和服务覆盖文件未离线取得，不能声称逐项
核验过现存配置；入场补只读清单。内核黑名单不依赖这些加载入口，若发现独立GPIO操作
服务则停止入场、离线审查，不现场扩大屏蔽范围。

**边界：这是禁止Linux无线初始化，不是已证明物理断电。** Wi-Fi/BT使用共享
vddao3v3/vddao1v8，仍有电；跳过probe也不保证主动拉低U-Boot遗留的使能GPIO。
lsmod/rfkill为空不能证明电流为零。GPIO/时钟只读状态若不可得，记未覆盖，
不临时请求GPIO或改方向。物理供电结论仍需独立测量。

## 封包身份和复现

原包、变体均为`7.3.1-vim4-20261106.36`，build ID
`355061dc85a2fd695429b501c0c2b87078cf1f89`。

| 对象 | SHA256 |
|---|---|
| 原RAM包 | ac15a2d07aaa58eb1d1b47d03ac30fb154f696e2aade40a13babea72bcb3fc84 |
| 变体RAM包 | 5d6e262cf6044e1cee23b65fd37dff6fb7ad82aba9ea2fb01dfa0d1065de3c6d |
| 原extlinux.conf | aff72f6c11f986dced0eecb1b6cd5faea24c5eed81b7c5ac8a622f783c85c9fb |
| 变体extlinux.conf | 639b4b8b37f3b8751257838e9279c2e2dde0106f4222475a6d5e6f9574f90bd5 |
| 变体trial.json | 0435be3035888a8d1b4f7265018c647de8746f36308486681f37cfb7d57d026f |
| 原构建manifest（未改） | 47e6faf309e33147f7b789ddce490ca44aa3bc44b431fd27744416ebac50fa1b |
| config（未改） | 7be7563e089ff628a320cd82ed163d88c576e4c7612f6bf849b230d2b9719b1c |

离线`prepare.py`只追加上述tokens并更新trial.json的extlinux摘要。
2357个普通文件逐字节相同，只有extlinux.conf和trial.json不同；后者唯一语义变化
是files中的extlinux哈希。`board-window.validate_bundle`实际通过，完整差异与核验
见同目录`extlinux.diff`、`identity.json`、`prepare.log`、`verify.log`。
变体保存为该目录candidate.tar，原包保留在integration36/candidate.tar。
沿用init内嵌的原候选暂存前缀，上传时整包重新核验，不能复用旧extlinux。
没有修改内核/DT，不重跑内核编译/KUnit；本次主仓库全套检查607项OK、11项跳过，
输出为同目录main-tests.log，跳过不计通过。

## 隔离范围与入场门禁

实际modules.dep中，dwmac-meson8b依赖stmmac-platform/stmmac/ptp，usb_f_hid依赖
libcomposite，aml-vdec-drv依赖v4l2-h264/t7-dos；均不依赖被屏蔽模块。
保留原以太网MAC、root/console、USB及解码参数。源代码/依赖证明路径独立，
192.168.50.210、SSH、HID和compliance实际可用性仍须下列板验，未提前记通过。

拟一张FIFO sampling票，目标20分钟、上限30分钟，**待批**；候选只启动一次，
不自动沿用r77的重试额度。预算：入场/上传4分钟，启动与身份4分钟，无线采证及
短解码5分钟，余量至绝对恢复边界；420秒恢复不可借用。进入HEVC前至少余3+7分钟。
完整HEVC全集不在本次提议清单内，变体成功也不自行续跑。

1. 正式uptime≥300秒、连续UART无新增复位；核正式fd41fb5身份及2372保护文件。
   核原/变体RAM摘要与输入SHA；计划protected_files逐项等于当前baseline.json。
   保存服务定义、modules-load.d/modprobe.d清单，确认没有额外无线GPIO上电入口。
2. 一次性sysboot加载候选extlinux，不改正式启动项、不saveenv。连续带宿主时间戳UART；
   SSH逐项核release、build ID、boot_id、完整cmdline含新增三项及原参数。
3. 候选ready和解码后各采lsmod、/sys/module、rfkill、dmesg、net/bluetooth设备与
   provider绑定、devices_deferred；预期brcmfmac/hci_uart/btbcm未加载，pwrseq-simple
   无绑定、SDIO deferred，无wlan/hci控制器和无线固件加载。记录initcall跳过消息。
   bluetooth.service临时mask生效。缺工具记缺失，但模块/绑定/固件路径未被阻断则判失败。
   可取得的GPIO/时钟状态只作辅助，不等同物理断电证明。
4. 核有线eth0的192.168.50.210、carrier/路由及SSH；核UDC绑定和既有HID功能/服务状态，
   不向Mac注入键鼠。运行stateless带流compliance/DOS=0，再按
   [integration36短清单](2026-11-06-vdec-integration36-plan.md)运行HEVC全I门禁及
   cip_B_NEC_3、MERGE_E_TI_3、TMVP_A_MS_3。保存I420、逐帧MD5、GST/ioctl/kernel日志；
   全I≥56/56、98304字节精确首帧/status0、事件顺序；三流5/8/17帧全同且status0。
   任一失败停止后续HEVC，不扩大输入。

## 停止、恢复与报告

任何Timeout/挂死、内核WARN/Oops/BUG、DMA/IOMMU/AXI异常、无线屏蔽门禁失败或恢复
异常立即收尾。候选冷复位不重试，分别记录Linux起点、ROM复位、最后日志和自然恢复。
剩余420秒强制进入恢复；持续正式冷复位最多观察两次自然启动，不主动reboot循环。

恢复正式`7.3.1-vim4-20261105`/fd41fb5，build ID
`bdbfa439f298e92b5bad092528d11119a974f262`，核2372 proof、视频推进及UDC/HID服务。
同时确认正式cmdline无新增三项，Wi-Fi/BT恢复原配置；不为本实验永久停服务。
清理前检查display-once.py helper，缺失时按原流程重传；只清任务所有且哈希匹配的
固件/候选上传，先归档校验、后删除，不动正式模块目录。密码只走stdin。

记录每次启动及冷复位、未运行项、无线初始化证据和电气状态的未覆盖范围。
即使一次成功，也只能证明本次变体启动/功能结果，不能证明供电假设或复位已消除。
