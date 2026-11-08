# 2026-11-02：BCM43752 下载吞吐与接收处理 CPU

默认 FullKvm 7.3 的 brcmfmac 使用 [.217 固件与配套模块](2026-11-02-wifi-fw217.md)。
在保存的 5 GHz 网络上，Mac 向板上 wlan0 发送单 TCP 流，接收端两次 600 秒
分别为 330.6、327.6 Mbit/s。5.15 的历史基准
为 418.9 Mbit/s。同期切换内核的短测也复现差距。

## 同一连接切换接收 CPU

板端 iperf3 使用反向模式，绑定 wlan0 和它的 IPv4 地址。SSH 管理走 eth0。
7.3 的 `brcmf_sdio_rxglom()` 拆开一批 SDIO 帧，逐包交给
`brcmf_netif_rx()` 和 `netif_rx()`。当 wlan0 的接收队列没有配置 RPS 时，
网络栈默认将包排到当前 CPU 的 backlog。RPS（Receive Packet Steering）
允许把网络层及 TCP 接收工作交给另一个 CPU，SDIO 传输仍由原驱动处理。

在同一次无线连接中，仅读写
`/sys/class/net/wlan0/queues/rx-0/rps_cpus`。默认掩码为 00，
04 选择 CPU2。每轮 30 秒，按实测顺序排列。

| 掩码 | TCP 流数 | 接收 Mbit/s | wlan0 收包/发包 | 每个 SDIO 聚合含包数 |
|---|---:|---:|---:|---:|
| 00 | 1 | 307.5 | 2.58 | 33.5 |
| 00 | 4 | 313.3 | 3.24 | 33.6 |
| 04 | 1 | 384.6 | 8.01 | 35.3 |
| 04 | 1 | 396.7 | 10.56 | 35.5 |
| 00 | 1 | 311.7 | 2.90 | 33.5 |

聚合含包数由 brcmfmac 的 rxglompkts 和 rxglomframes 增量相除。
五轮均无 rxglomfail 增量。网卡收发包比含全部流量。此前独立在 5.15 上
按开、关、关、开切换驱动的 TCP ACK 合并，关闭时仍达 430.8 和
433.6 Mbit/s，说明该开关不足以解释两版差距。

## 重启复测与内核路径

7.3 同一连接按 04、00、00、04 顺序各测 60 秒，接收端依次为
385.9、340.5、332.5、392.1 Mbit/s。切到 5.15 后，原厂配置的两轮
为 302.4 和 433.0 Mbit/s。原厂 wlan0 的 RPS 同样为 00，但厂商驱动
另有 dhd_dpc 和 dhd_rxf 线程。探针看到 dhd_dpc 执行 dhd_rx_frame，
TCP 接收则在 ksoftirqd 上执行。无线环境下每轮绝对吞吐有波动。

正常重启回 7.3，在同一连接按 00、04 各测 60 秒，得到 321.6、391.5 Mbit/s。
取每轮负载中的 80 毫秒样本，探针记录的是系统范围内 IPv4 TCP 接收入口：

| wlan0 掩码 | SDIO dataworker | tcp_v4_rcv |
|---|---|---|
| 00 | kworker/u35:0 | 1960 次中 1953 次在同一 kworker 上 |
| 04 | kworker/u35:0，样本落在 CPU1、3 | 2945 次中 2938 次落在 CPU2 |

串行执行 SDIO 收包和 TCP 接收是本板在单流下载时可重复消除的瓶颈。
RPS 允许二者并行，实验中没有调整无线射频、固件、SDIO 聚合或内核模块。
每次只对本机单队列设备改变 CPU 选择，连接期间恢复默认值会让吞吐回落。

## 板级配置与恢复

[板级 udev 规则](../../board/90-vim4-wifi-rps.rules)在 brcmfmac 注册
BCM43752 的 wlan0 时，通过标准接口为默认空的接收队列选择 CPU2。
在 VIM4 上 CPU0 至 3 是高性能核心，MMC 中断在 CPU0。
规则随板级安装脚本和 Ubuntu 板级组件分发，设备下次注册时生效。
驱动及其他集成平台仍可各自选择接收策略。
[Linux RPS 文档](https://docs.kernel.org/networking/scaling.html#rps-configuration)

回退手工部署时删除 /etc/udev/rules.d/90-vim4-wifi-rps.rules；对于包内规则，
在 /etc/udev/rules.d 下放置同名指向 /dev/null 的符号链接作为本机覆盖。
重新加载 udev 规则，向 wlan0 的 rps_cpus 写入 0 即可恢复当前设备的原始设置。

原始数据保存在本地 logs/wifi-download-ack/ 与 logs/wifi-rx-cause/。
matrix.log 为首轮短测，reverse.log、vendor.log、reboot.log 为带 CPU 探针的对照。
首次尝试 CPU 取样时 tracefs 不接受文件 seek，该段未计入结果。

## 持久安装后的 600 秒验收

板上 udevadm verify 通过；正常重启进入 7.3 后，wlan0 的掩码自动为
04，eth0 仍为 00。与之前的 600 秒基准使用同一 Mac、保存网络、方向和
单 TCP 参数，取接收端平均值。每个方向跑满 600 秒，60 个采样点均已连接。

| 方向 | 修复前两轮（Mbit/s） | 修复后（Mbit/s） | 5.15 历史值（Mbit/s） | 修复后 / 5.15 |
|---|---:|---:|---:|---:|
| 上传 | 333.1、346.8 | 316.4 | 296.8 | 106.6% |
| 下载 | 330.6、327.6 | 391.4 | 418.9 | 93.5% |

下载较修复前两轮均值提升 18.9%，低于 397.9 Mbit/s 的 95% 验收线。
上传也低于两轮旧值，本轮未隔离其原因。内核日志无新增固件崩溃；
unexpected txstatus 上传 46 条、下载 2 条。长测原始数据在
logs/wifi-rps-accept-Ko6I4G/。

另在相同连接按 04、0e、08、02、02、08、0e、04 各测 60 秒，结果为
386.3、393.0、411.2、388.8、372.3、347.0、397.3、373.2 Mbit/s。
两次 0e 的 TCP 取样都落在 CPU2，08 的两次结果跨过验收线的两侧。
未找到持续优于已通过长测的 CPU2 设置。保留 04。测试结束时 FullKvm
运行，Wi-Fi 关闭、默认路由 eth0，四项服务 active，UDC configured。
