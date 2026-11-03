# 2026-11-02：Wi-Fi 激活分组、TX status 7 与聚合上限对照

后续：[.217固件](2026-11-02-wifi-fw217.md)后114/114激活无新增转储，[SDIO主机路径](2026-11-02-wifi-sdio-host-path.md)同窗下载追平5.15并随[uhd7](2026-11-02-wifi-sdio-formal.md)部署；本文结论保留为当时证据，现状见[N03](../parity/platform.md)。

摘要：第四轮获准后共用板714.222秒（11.90分钟），全部票已释放。
固件/bin、NVRAM和CLM别名与厂商文件解析为同一文件且SHA相同；部署备份已删除。
基线5次激活崩溃1次，PM_OFF与P2P禁用组各0/5，但基线读回也已PM_OFF且存在固件重启混杂，
不支持据此实施PM或P2P修复。六次60秒上传采到24条状态7（106个完成条目），
对应固件DROPPED；聚合36没有提升，保持默认32，不新增行为补丁或部署。
历史、模块来源和离线假设见[主记录](2026-11-02-wifi-txstatus.md)、
[第三轮分析](2026-11-02-wifi-txstatus-offline.md)。

## 范围、身份与恢复

协调者明确此次获准后的所有票合计≤30分钟；此前轮次不占本轮额度。
板全程为默认FullKvm，release=`7.3.0-vim4kvm-uhd6+`，boot ID保持
`0edb0c34-6233-4fd0-a333-737b68c7860d`，未重启整板。
沿用日志overlay `0d0bdced8193be4169955ef21509a75d80bfd246`，未构建或部署新模块。
brcmfmac build ID=`da667c427b389418706c4de5107745a46531ac42`，COR仍为
`9b08acc2f8ce6ec746a59a4af4bf37565c8ed25d`；开始、两个成功窗口末尾均核对通过。

仅临时改已保存UUID `974bbec1-7e28-4f64-91b4-674c72bc37e9` 的NM powersave及
运行中的模块参数；未改AP、密码、固件或校准。组间关闭radio；模块参数用正常
`modprobe -r brcmfmac_wcc brcmfmac`、`modprobe brcmfmac txglomsz=… feature_disable=…`
加载，未强制卸载、未热重绑MMC。每次perf配置均从重新加载的固件开始。
结束用不带临时参数的modprobe恢复默认，连接powersave恢复原值0（default），radio disabled。
所有已登记boot artifact哈希核验通过，四项服务active、UDC configured、taint=4096（外部GPU标记）；
IPv4/IPv6路由与入场逐字一致，管理路由dev eth0。没有音频/HID、debugfs/regmap或ptrace操作。

## 具名输入与备份清理

以下为本轮读取的当前磁盘证据。`/lib/firmware`经系统链接解析到`/usr/lib/firmware`，
7.3三个别名分别解析到同表厂商文件；逐项复制到私有证据并核对SHA，完全一致。
既有5.15实际加载日志使用的正是这些厂商名字，固件版本两驱动均18.35.387.23.88 /
01-16e134aa；没有本轮重新启动5.15，当前哈希不冒充对历史读操作的重新观测。

| 厂商名（目录 `/usr/lib/firmware/brcm`） | 7.3别名 | bytes | SHA-256 |
|---|---|---:|---|
| fw_bcm43752a2_ag.bin | brcmfmac43752-sdio.bin | 820071 | af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309 |
| nvram_ap6275s.txt | brcmfmac43752-sdio.khadas,vim4.txt | 8358 | b5f24335121c042aad82bedc4300d0b65d250f978c675c43afea81d028aad5ad |
| clm_bcm43752a2_ag.blob | brcmfmac43752-sdio.clm_blob | 28865 | fc0bed644e599e622600431e7e3a11b5816dc7981f1a747c657475a3a761fabf |
| config_bcm43752a2_ag.txt | brcmfmac不解析该厂商配置 | 30 | ab1037877a80dffa6a677053694ff7b480607c527867d1a775529e976548ac00 |

配置内容仅`wl_preinit=pm2_sleep_ret=2000`。当前modprobe配置仅有dhd的厂商目录覆盖，
没有brcmfmac的txglomsz覆盖。7.3驱动/厂商构建不实际加载txcap的源码判断仍有效，
没有为消除日志伪造txcap文件。有效NVRAM转换结果和固件动态country/PMU状态仍未比对，
本轮同文件证明降低了“磁盘输入不同”的优先级，不能覆盖所有运行时差异。

在票467、激活前按用户偏好删除
`/var/backups/vim4-wifi-txstatus-0d0bdced8193`，末尾再次断言不存在。
历史部署收据的backup_path保留为当时事实，不改写成“从未创建过”；本轮未留部署备份。

## 基线、PM_OFF、P2P：每组五次

每次radio off→on，调用既有manager helper wifi-activate一次，成功后观察约5秒；
失败不在同一次中重试。每次记录状态、前后`iw … get power_save`、dmesg；
新崩溃等待保存器生成bin/json后，拷贝独立私有目录并归档到Mac，才开始下一次。
本轮总共只发生下面这一份新崩溃。既存转储入场也已保全，未依赖RETAIN=2维持所有样本。
实际顺序是先基线/PM_OFF，PM_OFF稳定后完成吞吐并恢复，再用独立票测试P2P禁用组；
吞吐没有混入P2P禁用配置。

| 分组 | 唯一请求差异 | 成功 | 固件崩溃 | 关键限制 |
|---|---|---:|---:|---|
| 基线 | 保持NM powersave=0及默认模块 | 4/5 | 1/5，第5次 | 每次激活前、成功后均读回off；失败后接口消失 |
| PM_OFF | NM powersave=2，helper前额外请求iw power_save off | 5/5 | 0/5 | 与基线实际读回状态没有on/off对比；在基线崩溃自动恢复后执行 |
| P2P禁用 | 模块feature_disable=16；NM恢复0，txglomsz=32 | 5/5 | 0/5 | 新加载固件后执行；仍读回off；真实peer不测 |

不能把1/5对0/5说成明确因果，分组顺序及固件新旧上下文也不同。
**单纯PM_OFF不足以避免本次故障**：基线第5次helper前已经读回off仍崩溃；
这不排除MPC/核心时钟或更早PM切换时序。没有强制PM_ON对照，不宣称完成了该对照。
P2P 0/5也不是修复证明；没有永久屏蔽能力。

新样本`wifi-1793597953386383791-devcd1`：

```text
bin  e11d4b52b0f9bf00389e8e76797d6b7034c4b09d6da029f841126ed0087426af
json d23cf65b52ac0c46e439986f800d3b668b9e0fb7d1e6b23613bcb9e0c40a7f6f
```

RAM解析：shared=0x1f1714、flags=0x100401、assert三字段零；main_thread run cnt6454，
固件uptime1104.712秒，TRAP4，PC=0x6e55c、LR=0x6e551、SP=0x2afbf8，DFSR=0x1c06、
DFAR=0；AXI addr=0x180013fc、flags=0x01111200、status=1。
PC/LR/SP及AXI写异常均与[历史A](2026-10-22-wifi-coredump-analysis.md)相同，
支持同一类D11/PHY访问路径故障，不只是“类似日志”；仍缺触发命令和trap瞬间电源状态。
发生在存活约18分钟的固件中，也不能简单归为仅冷启动前4秒的问题。

## txglomsz 32/36：交错三对上传

PM_OFF组稳定后按32→36→32→36→32→36执行，均为STA、P2P默认开启、NM powersave=2，
读回off；每轮先重新加载相同模块、连接同一5GHz AP，再单TCP上传60秒。
Mac `192.168.50.239:5210`；板iperf仍绑定无线IP与`--bind-dev wlan0`，有线管理保持。
此为诊断短测，不替代600秒验收，也不是与厂商在同一时段的配对。

| 顺序 | txglomsz | 接收Mbit/s | TCP重传 | 状态7日志条数 | compcnt之和 |
|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 255.626 | 0 | 0 | 0 |
| 2 | 36 | 252.158 | 0 | 4 | 35 |
| 3 | 32 | 256.798 | 2 | 1 | 2 |
| 4 | 36 | 254.233 | 0 | 15 | 44 |
| 5 | 32 | 258.290 | 0 | 0 | 0 |
| 6 | 36 | 250.933 | 2 | 4 | 25 |

32组均值256.905、中位256.798Mbit/s；36组均值252.441、中位252.158Mbit/s，
均值比98.26%（约低1.74%）。本轮没有支持“把32改36即可补齐差额”的证据，保持32。
相对之前厂商上传296.810，本轮32均值约86.56%，仍不支持95%验收；
短测/跨轮混杂不支持精确量化驱动差额。
六轮无新崩溃、WARN或hanger缺包错误；吞吐区间没有新的SG告警，但warn_once无法给出回退比例。
未采MMC trace、全系统CPU或credit等待，不把该负结果扩展为排除所有SG/调度瓶颈。

### 实际TX status语义

所有24条均为`flags=7`；32组三轮合计1条、compcnt=2，36组三轮合计23条、compcnt=104。
因此对应106个完成条目，不能只按24条当成24个包，更不能等同TCP重传数。
其余激活分组未出现未知状态日志。
厂商`include/wlfc_proto.h`定义7=`WLFC_CTL_PKTFLAG_DROPPED`，描述为固件因其他原因丢弃；
厂商处理器累加pkt_dropped并完成包，brcmfmac打印未知状态后同样走非suppression完成路径。
直接机制是固件合法状态值未在brcmfmac枚举/统计分支覆盖，**不是可宣布无害的正常ACK**，
也不证明状态7触发了AXI崩溃（本轮崩溃前没有该日志）。
增大聚合上限时这些状态更多，仅为本轮关联，不足断言36超过固件硬上限或锁定drop原因。
此任务的行为修复门槛未满足，不改credit、完成语义、枚举或屏蔽日志。

## 计时、证据与交付边界

所有访问经`tools/board-queue run --who wifi-txstatus`，以下为共享history的持票时长，
包括失败、取证、清理和模块参数恢复，不只计算流量时间：

| 票 | 秒 | 结果 |
|---|---:|---|
| 466 | 1.650 | NM枚举格式前置校验失败，未激活、未修改profile；radio仍关闭 |
| 467 | 607.033 | 输入/删除备份、基线与PM_OFF各5次、六次上传、恢复与核验 |
| 468 | 105.539 | 单独P2P禁用5次、恢复默认模块/连接设置、核验 |

合计**714.222秒（11.90分钟）**，低于本次获准后总额30分钟，全部已释放。
不再因剩余预算而扩大分组或反复触发故障。没有新增内核提交/部署：VM分支wifi-txstatus
仍为0d0bdced8193be4169955ef21509a75d80bfd246。

原始证据私有留在`logs/wifi-txstatus/round4/`，含preflight、每次attempt JSON、六轮
iperf、每次dump归档、最终状态与`summary.json`；两个窗口日志为上一级
`round4-window-r2.log`、`round4-p2p-window.log`，失败票日志也保留。
分组结果不足支持PM/P2P行为修复；数据输入差异与聚合上限32过小两条假设已降级。
剩余是D11/PHY访问的精确主机时序、MPC/核心状态与吞吐的实际调度/SG成本。

验证入口：`python3 -m unittest discover -s tests -p 'test_*.py'`、`git diff --check`；
最终日志留在`logs/wifi-txstatus/round4/unittest-final.log`。
