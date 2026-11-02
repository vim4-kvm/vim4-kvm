# 2026-11-02：BCM43752 第三轮离线差异与验证草案

摘要：三份RAM中的SI核心表及保存的EROM字段证明0x18001000为D11 rev82；
0x3fc为公开D11定义的PHY间接地址端口。崩溃最符合固件PHY访问与连接/电源状态失配，
尚未锁定具体iovar。吞吐首先应验证批处理/SDIO路径，不能从32/36包推算85.7%。
本轮不占板、不部署、不改VM代码。上板与转储身份见[主记录](2026-11-02-wifi-txstatus.md)。

## 样本与来源

源码版本同主记录：主线0d0bdced8193、厂商80a07ad5406d、common_drivers 563cff9dab2c。
只读VM源码/既存`.cmd`，不调用板队列、SSH或板接口。
证据在忽略目录`logs/wifi-txstatus/`，补充源码/摘录/脚本在其`round3/`，RAM不公开。

## 1. 固件、NVRAM、CLM、txcap：相同与未知

以下路径均相对`/lib/firmware/brcm/`。L为实际启动日志/取回哈希，S为源码或历史安装合同；
版本串相同不等于文件哈希相同，安装器期望值也不冒充本轮文件实测。

| 项 | 5.15实际日志 L | 7.3来源及已知哈希 | 判断 |
|---|---|---|---|
| 固件 | `fw_bcm43752a2_ag.bin`，820071 bytes；18.35.387.23.88 / 01-16e134aa | `brcmfmac43752-sdio.bin`，本轮L哈希F；历史S为前者别名 | 版本、预期来源一致；缺本轮厂商路径的独立哈希，未证明逐字节相同 |
| NVRAM | `nvram_ap6275s.txt`，8358 bytes；AP6275S_NVRAM_V1.3_20200922 | `brcmfmac43752-sdio.khadas,vim4.txt`，历史S别名/期望哈希N | 没有本轮双方txt原件/readlink/哈希，不声称已核对有效参数相同 |
| CLM | `clm_bcm43752a2_ag.blob`，28865 bytes；9.9.5_SS (2019-12-04 01:26:12) | `brcmfmac43752-sdio.clm_blob`，历史S别名/期望哈希C；当前日志无缺失错误，未打印clmver | 缺本轮两端文件哈希及7.3 clmver |
| 额外配置 | `config_bcm43752a2_ag.txt`，30 bytes，L：`wl_preinit = pm2_sleep_ret=2000` | brcmfmac不解析此bcmdhd配置文件 | 确认额外主机配置入口不同；不能仅凭此说PM值不同 |
| txcap | S：本构建无`CACHE_FW_IMAGES`，`dhd_apply_default_txcap()`走返回0的stub；无下载日志 | S：SDIO `get_blob()`只支持CLM，TXCAP返回-ENOENT；L：“no txcap_blob” | 7.3该信息不证明磁盘文件缺失；也未发现厂商实际加载txcap的证据 |

`prepare-wifi-firmware.py`保存的历史校验合同：

```text
F af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309
N b5f24335121c042aad82bedc4300d0b65d250f978c675c43afea81d028aad5ad
C fc0bed644e599e622600431e7e3a11b5816dc7981f1a747c657475a3a761fabf
```

`firmware.c:brcmf_fw_nvram_strip()`去注释、转NUL并可补boardrev/平台MAC；厂商也会转换
NVRAM。txt哈希相同仍需比较有效键值。dump末尾已复用为shared指针，无法恢复完整txt。

下次获准上板时只读具名文件：上述四个厂商文件及三个brcmfmac别名，分别`readlink -e`、
`stat`、SHA-256；取回txt/config/clm原件私有比对。读
`/sys/module/dhd/parameters/{firmware_path,nvram_path,clm_path}`与
`/sys/module/brcmfmac/parameters/{alternative_fw_path,roamoff}`核对覆盖项。
7.3 SDIO没有请求txcap文件名；不能虚构一个“实际加载路径”。只有确认确有txcap路径覆盖
才读取那个具名文件。CLM版本可用已审核的具名`clmver`查询，不读debugfs。
在读取前删除已知部署备份目录`/var/backups/vim4-wifi-txstatus-0d0bdced8193`，
这是协调者指定的下次上板清理；本轮未删除，历史收据不改写成“未留过备份”。

## 2. 从RAM核心表确认地址归属

三份bin先验证主记录/10-22公布的完整SHA。RAM基址0x170000，长0x140000。
转储中0x1f1c00指向0x1f1c5c，0x1f1bf4为12；后者与邻接si_info的numcores布局吻合。
依bcmdhd `siutils_priv.h:si_cores_info_t`、`hndsoc.h`的_RTE_ `SI_MAXCORES=16`，
32-bit指针下解出六组数组：regs +0、coreid +64、coresba +128、wrapba +512、
cia +832、cib +896。对12个条目逐项验证regs=coresba、CIA组件号=coreid；
CIA/CIB格式与主线`chip.c:brcmf_chip_dmp_erom_scan()`的掩码一致，三份表完全相同。
这利用的是固件保存的EROM扫描结果，不是声称dump含0x18000000处的物理EROM本体。

| index | core ID / 名称 | base | rev |
|---:|---|---|---:|
| 0 | 0x800 ChipCommon | 0x18000000 | 65 |
| 1 | 0x812 D11/802.11 MAC | 0x18001000 | 82 |
| 2 | 0x83e ARM CR4 | 0x18002000 | 16 |
| 3 | 0x83c PCIe2 | 0x18003000 | 65 |
| 4 | 0x829 SDIO device | 0x18004000 | 26 |
| 5 | 0x844 M2M DMA | 0x18005000 | 2 |
| 6 | 0x840 GCI | 0x18010000 | 15 |
| 7 | 0x827 PMU | 0x18012000 | 35 |
| 8/9 | 0x841 Save/Restore | 0x18013000 / 0x18018000 | 7 |
| 10 | 0x240 AXI/AHB bridge | 0x19000000 | 0 |
| 11 | 0xfff default component | 0x00160000 | 0 |

D11的wrapper=0x18101000，CIA=0x4bf81201，CIB=0x5208c431；
`(CIA&0xfff00)>>8=0x812`，`CIB>>24=82`。si_info当前映射字段亦为D11 base/wrapper。
公开[Linux/Broadcom d11.h](https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wireless/broadcom/brcm80211/brcmsmac/d11.h)
定义16-bit `phyregaddr`=0x3fc、`phyregdata`=0x3fe。因此errlog地址落在D11的PHY间接端口，
不是ARM或PMU核心寄存器；console的“CoreID:135”不直接当成这张表的core ID。
旧头文件未穷尽rev82语义，PHY索引/ROM函数仍未知；核心表不证明trap时已断电，非法PHY索引亦未排除。

复核命令为`python3 logs/wifi-txstatus/round3/analyze-cores.py`，输出`core-map.json`；
样本哈希、指针/边界、CIA/base及三份表一致性通过。未取得符号化调用栈或新的反汇编结论。

## 3. 初始化/连接差异：事实不直接等于首因

仅标L者为实测，其余为编译路径/默认值，可能被NM/固件覆盖。

| 项 | 5.15 bcmdhd | 7.3 brcmfmac | 对归因的意义 |
|---|---|---|---|
| SDIO时钟/宽度/F2 | L SDR104/200MHz/F2=256；DT 4-bit | L SDR104、112/256告警；DT 4-bit/200MHz上限；bcmsdh.c选择256 | F2未用错512；缺7.3实际ios时钟 |
| SR/KSO | dhdsdio_sr_init支持43752，L slpauto=1；FORCE_HT、CMD_NODEC | chip_sr_capable读PMU retention，SR设FORCE_HT/CMD_NODEC，bus_sleep切KSO | 均支持低功耗；缺运行时序 |
| PMU | BCMDONGLEHOST下排除完整PMU/PLL/res_init；min mask函数无43752分支 | 不写43752 min/max mask，设置reset reload，固件管理资源 | 不能将hndpmu.c函数当成主机必需操作或照抄其他芯片掩码 |
| 下载前D11 | dhdsdio_download_state的CR4路径只halt/reset ARM | chip_cr4_set_passive显式disable D11，由固件enable | 真实差异；trap在37秒后，不证明核心从未启用 |
| PM/MPC | PM_FAST；cfg80211连接后PM_OFF、延后10秒恢复；L pm2_sleep_ret=2000 | preinit mpc=1；config_dongle立即按pwr_save设PM；扫描MPC保护仅4329；PM timeout上限也2000 | 有时序差；不能说主线缺2000配置；NM最终调用未知 |
| join/SAE | SET_CHAN_INCONN；L join前设5g40/80MHz；assoc_mgr外部认证 | join携带信道，无同样独立chanspec预设；WCC assoc_mgr_cmd暂停/恢复/发帧 | 可能进入不同PHY路径，缺崩溃前命令序列 |
| country/roam | L CN/0，6GHz bw_cap=-13；roam_off默认1 | 暴露2.4/5GHz，无43752 ISO fallback；roamoff默认0 | 无主线6GHz发射证据；最终country/roam待查，不改地区/功率 |
| host TX | L copy36，连续buffer后CMD53；SDALIGN32，预算TX64/RX128 | txglomsz32、ALIGNMENT8、skb SG；预算TX20/RX50，rxpending压低TX | 批量/调度/fallback候选；32/36非吞吐公式 |
| bus方向/水位 | bus:rxglom=1；core26不走旧水位补丁；txglomalign为SDALIGN | bus:rxglom=1，txglomalign默认8；F2WM0x40、F1 MESBUSY | bus:txglom指FW→host，不是host TX；不推定水位导致AXI |
| 空口/credit | L hostreorder tlv64、wlfc_enable；S ampdu_mpdu32/txack_alive0/TCP ACK replace | WCC自动explicit-credit；无前述ampdu/txack配置和ACK替换 | 需查有效值；ACK替换更可能影响下载 |
| frameburst/txbf | 均1 | SET_FAKEFRAG=1、txbf=1 | 已一致，缺失假设不成立 |

关联瞬间均5200MHz，7.3约-36dBm/1200.9Mbit/s，厂商-33dBm/1200.5Mbit/s，非全窗速率序列。
缺batch/credit等待/回退比例及全系统CPU；射频、背景业务、调度仍混杂85.68%的单样本比较。

## 4. 排序假设、最小实验与条件成立后的修复草案

没有一个假设已达到部署行为修复的证据门槛。以下均是**收到“可以上板”后**的候选，
本轮没有运行。只用保存的STA/AP及既有密码，不改地区/功率，不发HID、不测音频。

1. **连接/扫描的PHY上下文与省电切换失配（中等，崩溃首选）**。
   强依据为D11 PHY端口AXI异常、流量前trap、厂商显式信道预设/延迟PM，而非TX包负载。
   缺口是崩溃前的命令名/ifidx/返回时序。
   最小实验：同一模块/固件baseline五次激活对比“仅PM_OFF”五次，采集UP、scan、join、
   assoc_mgr、PM及其fwerr时间；若trace显示是discovery先失败，再单独比较临时禁P2P五次，
   不能将禁P2P和PM_OFF合成一个配置。每次dump私有归档后才进行下一次，不让轮换覆盖。
   若PM分组有效，草案是在已有CONNECTING/CONNECTED事件中延后恢复所请求的PM，完成/失败
   退出均恢复既有设置；若只与pre-join信道有关，草案为WCC/该FWID的已知目标信道设置顺序，
   不在通用cfg80211强制固定信道。不能用“永久关MPC/P2P”冒充最终修复。
2. **D11初始reset/clock所有权与旧固件不匹配（中低，崩溃第二候选）**。
   两主机下载路径确有差别，RAM表证明具体D11，但没有trap瞬间的reset/clock状态。
   最小实验：单一诊断模块仅对43752保持厂商CR4下载入口行为，其余逻辑不变，比较五次激活
   与已采baseline；不手工访问PHY/MMIO。若有效，上游草案是chip-specific passive/reset
   quirk及明确固件所有权注释，保留其他芯片特别是现有BCM4387规则，并验证恢复下载。
   不给MAC/PMU写一个猜测常量。若无效立即放弃这条变更。
3. **host批量/调度与MMC SG路径造成吞吐差（中等，性能首选；不解释PHY trap）**。
   厂商copy36/预算64、主线SG32/预算20和已见fallback是实证差异，实际占比未知。
   最小实验：连接稳定后txglomsz32/36各三轮60秒上传，交错顺序、同AP/同PM/同credit模式，
   每轮保留PHY速率/重传/接口计数和/proc CPU/softirq；独立5秒采现有MMC request/done
   trace的blocks/blksz/bytes/耗时，不在正式吞吐段开高频trace，不读debugfs。
   参数无效/batch未到上限则实验无效；MMC trace无SG长度/回退标志，不能计算bounce比例。
   若batch上限成立，草案限该芯片/固件的聚合参数；
   若定位到调度饥饿，修已有TX/RX预算选择。copy路径需先证明耗时再评审，不复制整套bcmdhd。
4. **输入数据/监管或实测运行模式不同（低，先排除的证据缺口）**。
   版本/来源相同而缺txt/CLM和厂商bin独立哈希；country/roam/PM覆盖未取回。
   实验为第1节具名文件/iovar及有效NVRAM diff；
   若确有不一致，先修镜像别名/板型选择或已证实的解析缺陷，不另选固件、不改校准。
   一致即降级；roam不同不能单独证明AXI根因。

下一板窗**总预算≤30分钟**：身份/具名文件与备份清理3分钟；假设1基线及PM分组4分钟；
按证据只选P2P分组或假设2模块对照4分钟；稳定后假设3性能8分钟；证据和FullKvm恢复5分钟，
余6分钟供恢复；超预算停止后续实验。使用已验kernel-select，不新增回退脚本。
报n/5及失败阶段，0/5不保证崩溃率为零；新鲜/恢复后连接分报。

本轮仅提交证据和草案，VM HEAD/部署模块均未变。未申请板票，上板0秒，备份清理仍待授权窗口。
