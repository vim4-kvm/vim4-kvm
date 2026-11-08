# 2026-11-05：TCPM 冷复位专项分析与正式启动记录

结论：PD 接管导致掉电仍是假设，尚无实际 Hard_Reset 或 VBUS 下降证据。上游已有
非自供电 sink 的 Get_Source_Cap 恢复步骤，因此不能把 Accept 后的 310 ms 超时直接
等同于 Hard_Reset。FUSB302 有对应的 RX FIFO 排空待审补丁，值得优先审查移植。
本轮只分析和读 journal，未改 DT/驱动，未重启；改动方案须经协调者批准后实施。

前序：E1、
[时序](2026-11-05-adla-mutex-pd-timing.md)。UTC。

## 状态机核对

检查部署基线 `2662456a1a636`，`v7.3`（`c03c1a14507dfaf8b856c2608f9ac216021fc222`）
与 `v7.3.1`（`79a907609d53d5cd645b42c11550d295d43abf99`）。部署 tcpm.c 与两 tag
相同；以下行号按部署文件 `drivers/usb/typec/tcpm/tcpm.c`。

1. `SNK_WAIT_CAPABILITIES`（5838）：使能接收；VBUS 从未低过时先等待一次
   `sink_wait_cap_time`，然后 Soft_Reset，且只走一次该接管恢复。
2. `SOFT_RESET_SEND`（6213）发送失败立即选择 hard_reset_state；发送成功先等
   `PD_T_SENDER_RESPONSE`。本树为 60 ms。收到 Accept 后回 SNK_WAIT_CAPABILITIES，
   不再使用上一步等待 Accept 的期限。`.83` 已观察到这个返回。
3. 非 self_powered 的 sink 再等 310 ms 后进入 `SNK_WAIT_CAPABILITIES_TIMEOUT`
   （5863），发送 **Get_Source_Cap**。发送失败立即选 hard_reset_state；成功则再等
   310 ms，期间 Source_Capabilities 可使状态机转入能力协商。故通常是 Accept 后
   两段等待加发送耗时，不能省略中间报文。已有
   [上游恢复修复 122968f8dda8](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=122968f8dda8205c5735d7e1b1ccb041a54906d1)。
4. `hard_reset_state`（5285）在 hard_reset_count 小于2时选 HARD_RESET_SEND；超限且
   PD capable 则 ERROR_RECOVERY，未识别为 PD 的等待能力 sink 则 SNK_READY。
   计数在 HARD_RESET_START（6073）递增，协商能力时归零；掉电丢失计数，不能靠它防开机循环。
5. HARD_RESET_SEND（6061）对非自供电 sink 打印
   `Initiating hard-reset, which might result in machine power-loss.`，再发协议复位。
   HARD_RESET_START 禁 PD RX，sink 进入 SNK_HARD_RESET_SINK_OFF（6123）：代码明确
   不主动 discharge/disconnect，但不能阻止远端 source 因 Hard_Reset 移除 VBUS。
   其后等待供电恢复；板已掉电时不能执行恢复步骤。

`.83` 完成→Accept 4.996 ms，未超过60 ms；之后只采到安排310 ms，无实际到期、
Get_Source_Cap、Hard_Reset 或 VBUS low。Accept 日志串口块→ROM 1.050216 s 不能定因。
E1未采到Accept；正常 `.3` 也等310 ms再Soft_Reset，调试probe较晚不等于协议超时。

## DT 能否正规免除掉电

实际部署使用 fixed-peripheral profile：
`arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-udc-test.dts:5`
使能 typec；其包含的 VIM4 dts:691 connector 是 sink/device、固定 5 V/3 A PDO，
没有 self-powered、pd-disable、sink-vdos 或覆盖等待时间。普通 dts 的 disabled 状态
不能代表实际部署状态。

对照 [v7.3 usb-connector binding](https://github.com/torvalds/linux/blob/v7.3/Documentation/devicetree/bindings/connector/usb-connector.yaml)：

| 属性 | 代码含义与本板结论 |
| --- | --- |
| self-powered | 声明设备有独立电源（binding:49，tcpm:8326）。本板只确认 USB-C 单线供电，不能虚报；设 true 还会跳过上述 Get_Source_Cap 保护步骤，更早选择复位。 |
| sink-vdos / sink-vdos-v1 | 可选 Discover Identity 响应身份数据（tcpm:8477）；不控制 Hard_Reset 或供电保持。 |
| sink-wait-cap-time-ms | 合法范围 310–620 ms（binding:256，tcpm:8138 读取）。只能改变等待期限；不能找回 FIFO 积压，也不保证 source 不自行复位。没有实测依据支持改本板值。 |
| pd-disable + typec-power-opmode | 声明端口无 PD，tcpm:5809 直接进入 SNK_READY。不是保留现有 PD 功能的免复位选项；既有固件合同、source 行为、默认电流和 USB 能力仍须另验。当前未满足 E2 的供电前提，不建议试。 |

未找到“保持完整 PD 协商且对 VBUS-only sink 永不 Hard_Reset”的通用 DT 开关。
SNK_HARD_RESET_SINK_OFF 的保护仅管本地动作；即使禁止本端主动复位，也不能保证
远端不发复位。不能通过虚报 self-powered、PDO 或静默延长/删除协议恢复来宣称修复。

## FUSB302 收包路径与上游来源

部署 `drivers/usb/typec/tcpm/fusb302.c`：request_threaded_irq（1798）主处理函数为
NULL，线程中的 fusb302_irq_intn（1487）disable_irq_nosync，再把实际 I2C 操作排入
系统 workqueue。irq_work（1505）在 chip mutex 下依次读取清零的中断快照；TX_SUCCESS
（1606）和 GCRCSENT（1626）各调用一次 read_message（1434），结束才 enable_irq。
每次 read_message 消费一帧，再按真实 header 将 GoodCRC 交 TX completion、其他交 TCPM。
现有乱序事件处理不等于排空 FIFO；整个工作函数不检查 RX_EMPTY。

据 [onsemi FUSB302B 数据手册](https://www.onsemi.com/pdf/datasheet/fusb302b-d.pdf)
表35/36，中断是 read/clear 位，表38提供 RX_EMPTY/RX_FULL。单个位不是报文计数器：
如果读取快照前多个接收事件合并，而 FIFO 中帧数多于本次两位对应的消费次数，可能留下
未读帧且没有新的中断通知；后续接收再唤醒时读出的又是旧帧。高延迟增加这种机会，
不要求已经发生 FIFO 溢出。手册另说明接收 FIFO 不及时服务可能停止自动 GoodCRC。
这些是路径风险，不证明本次 Source_Capabilities 已上过线或已进 FIFO。

另排除一个误判：set_pd_rx（842）在 pd_rx_on 不变时直接返回，只有改变使能状态才
flush。`.83` Accept 后回等待能力时是 `pd is already on`，不能称这一步把能力帧冲掉。
该次末尾两个快照分别 a=04/b=00、a=00/b=01，读到了 GoodCRC 和 Accept；它们本身
不证明多帧合并。没有 Source_Capabilities/FIFO occupancy 的尾部可继续核对。

2026-11-05 检查的树与快照：

| 树 | HEAD |
| --- | --- |
| mainline | 05441d697f7f9a927264f4058cbbc6a03dfcac9d |
| linux-next | 8b7179210b22f8e48a82c5ceacb9d56a9c4cfec4 |
| gregkh/usb usb-next | 6628e7d4c6b25c8d18f1345e3a20d21829aae7e4 |

三棵树的 fusb302.c 均与 v7.3.1 相同，尚无排空修复；上述 TCPM 等待能力分支也相同。
发现 Alexey Charkov 11-02 的邮件
[Drain the RX FIFO on each PD interrupt](https://lore.kernel.org/linux-usb/20261102-fusb302-drain-rxfifo-v1-1-bd9b232ab345@flipper.net/)：
增加按 RX_EMPTY 排空的有界循环。lore 正文直取403，通过[邮件镜像](https://lore-kernel.gnuweeb.org/linux-usb/20261102-fusb302-drain-rxfifo-v1-1-bd9b232ab345%40flipper.net/)
搜索正文读到 diff 和三封线程；未合入，三棵树源码另行核实。
[作者回复](https://lore.kernel.org/linux-usb/CAKTNdwGSxPyuadpQPY5oDRHwC_HTX7BujSCM-bRiKgjnyicDvQ@mail.gmail.com/)
还明确：对于硬件不应答的 Get_Source_Cap_Extended，需要配套
[Drop unacknowledged Get_Source_Cap_Extended](https://lore.kernel.org/linux-usb/20261102-fusb302-getsourcecap-v1-1-26b5bfea4b2b@flipper.net/)，
避免排空后把未确认帧交给 TCPM，产生不合时宜的响应。该硬件特性来自邮件报告，本板
尚未观察到 type17。未查到本线程维护者 Ack/合入或后续版本，不把作者/机器人回复当认可。
同期长 SMBus TX 补丁解决大于5个数据对象的发送，当前控制帧/单 PDO Request 不触及。

## 正式 .3 的只读启动统计

本节为历史口径；最新正式包 RAM/eMMC 复位与分母见[r60](2026-11-05-vdec-coldboot-ab-r60.md)。

只读票 `b37e4690e1aa450a9e6ad616082e1ca2`，12:14:45–12:15:55，约70.2秒。
执行 list-boots，逐 boot 提取 Linux version、末35条和 shutdown/reboot 标记；前后均
正式 `.3`，boot_id `bf5454df-a33d-446e-95b9-a67b8067d178` 未变。没有 RAM 启动、
硬件寄存器读取、服务变更或主动恢复。首次约1秒短票因 journalctl 不支持 --no-legend
结束，未取得清单；离线移除选项后重新 FIFO 采集，未把错误当作零 boot。

现存34 boot，覆盖约09:35至采集时刻。20个可确认为正式 `.3`：16个有 Linux version，
4个早期 kernel 记录缺失，用本任务前后采证 JSON 的 release/boot_id 补齐。
其中17个有正常 shutdown/reboot 尾部，2个早期中断，1个仍在运行。其他14个包含调试、
生产候选及5.15，不能纳入正式 `.3` 分母。

逐次 boot_id、UART 主机时戳和分类见[冷复位统计表](data/2026-11-05-tcpm-coldboot-events.csv)。
其中前两条是本次正式 `.3` 统计的 7.428245/7.517541 秒事件。
后追加的 r51 `.28` 是生产配置候选，启动约6秒
回 ROM（末条内核时戳5.540308秒，缺逐行主机时戳），不加入上述正式 `.3` 分母。

异常 journal 最后 monotonic 为5.517813/5.541635秒，比 UART 早停，不是复位瞬间。
后者 FIRST ENTRY 为10-12，LAST ENTRY 落在11:51，有校时跳变，不能按其墙钟排序推算
间隔。三个自有窗口事件另存 uart-boot-events.json；`.81` 恢复未见额外复位。

近期已结束19次正式启动中2次非请求早期复位，约10.5%；含当前运行的20次则10%，
当前启动右删失。两次集中于启动约7.5秒，不能外推全天/稳态故障率。其他任务有计划
重启；更早及超早未落盘记录可能缺失，缺关机尾部不自动证明异常。

## 待审方案、预期与验证

建议先审上游 **RX FIFO 排空与未确认 Get_Source_Cap_Extended 配套处理** 两个补丁，
按作者拆分保留身份、Signed-off-by、Link；取得原始邮件后核对完整正文及依赖，再移植。
目前没有可 cherry-pick 的已合入提交；不能用机器人引用的临时 commit 当正式上游来源。
仅针对 FUSB302 收包，不改 TCPM 超时/Hard_Reset 策略、DT、电源角色或 PDO。
预期：一次工作可处理积压的 GoodCRC/Accept/能力帧，按真实 header 分派；未确认的
type17 不触发协议响应。仍不保证远端会发能力或保证整板不断电。此为待批准方案，
不是本轮已实施的修复，也未认定为本板冷复位根因。

批准后用 KUnit 可控 I2C 返回值测真实 FIFO 消费及 TCPM 通知：合并事件下
GoodCRC+Accept+能力帧、空 FIFO、I2C错误、循环上限及 type17；再做 strict checkpatch、
模块/内建 W=1+sparse、arm64 QEMU。heavy暂停期间不构建，统一候选由集成构建者准备。

下一次批准的 PD 专项 RAM 窗口先书面确认变量与脚本，采完整 UART 主机时戳、驱动现有
软件日志，并尽可能由外部仪器观察 CC/实际 VBUS/RESET。软件记录须区分 Get_Source_Cap
实际 TX、超时实际执行、HARDSENT、收到 Hard_Reset、VBUS低与新的 ROM，确认因果顺序；
不另用原始 I2C 抢读清零状态。若没有物理观测，只能报告软件路径改善，不能定性掉电。
首错停止、回正式 `.3` 验视频，不为凑频率连续重启。尚未执行新的专项窗口。

集成 A 要零 lockdep/KASAN/DMA-API、debug_locks持续1、ADLA/Wi-Fi及eMMC/SDIO；
B 正式配置600秒 TCP 接收对照369.55 Mbit/s，每窗回 `.3` 核视频。等待统一候选，未验。

证据在本工作树 `build/debug-splat-fixes/pd-audit/`：journal-audit.json、journal-summary.json、
uart-boot-events.json、部署与上游源码、fetch.json、pinned-source-verification.json；
脚本/SHA/板票见任务 result，UART 为 logs/debug-splat-{a81,a83,e1}/。
未改内核，编译/KUnit/性能未运行；主仓库检查见提交说明与 result。
