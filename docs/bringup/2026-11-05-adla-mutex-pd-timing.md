# 2026-11-05：ADLA 锁类修复与 PD 启动时序比较

ADLA 初始化锁类修复已独立提交 `53d7db5f377e86998295aeb082eedba3aec108de`，
真实包装 API 的 arm64 QEMU KUnit 通过1/1。生产 `.3` 也会等待310ms后 Soft_Reset，
因此已有调试日志不能证明“KASAN 拖慢导致 PD 超时、Hard_Reset 掉电”的因果链。
没有修改 PD 代码。调试 `.83` 再次 cold_boot，未完成A门禁；已恢复 `.3` 和4K视频。
生产 `.84` 按协调者新指示不单独上板，后续A/B统一使用集成候选。

后续Wi-Fi probe排除实验仍复位，另观察到
自动回 `.3` 后的一次未请求复位；E2因默认供电前提不能确认未执行。
后续[专项审计](2026-11-05-tcpm-coldboot-audit.md)还从本记录 `.83` 的恢复UART确认
正常恢复请求之后 `.3` 在启动7.428秒自行再复位，最终恢复证明仍有效；近期共确认两次。

此前 `.81` 的原始失败、容量事故及 `.3` 恢复证明见
[首次实板记录](2026-11-05-debug-splat-board-validation.md)。

## ADLA 修改与来源

公开主线/linux-next/misc 维护者树没有这套下游 ADLA OS 层；本轮 exact-symbol
和 lore 的 ADLA/mutex 检索未找到可移植修复。按现有 `mutex_init()` 调用点分类机制
自写修复，没有伪造上游提交。lockdep 区分类与实例的规则见
[内核锁验证文档](https://docs.kernel.org/locking/lockdep-design.html#lock-class)。

原包装函数在 `drv/port/os/linux/adlak_os.c` 内统一调用 `mutex_init()`，使 dev_mutex、
SMMU mutex 等不同角色共享一个静态 key。启动时 `adlak_device_init()` 持 dev_mutex，
再由 `adlak_mem_smmu_init()` 获取另一个 SMMU mutex，触发错误的递归类报告。

现在分配保留在 `adlak_os_mutex_alloc()`，`drv/port/adlak_os.h` 的
`adlak_os_mutex_init()` 宏在实际调用点展开 `mutex_init()`。不同初始化点得到不同
静态 key，同点创建的实例仍共享类、照常检查依赖；没有使用 nested、动态每实例类、
lockdep_off 或改变调试配置。句柄、分配失败返回值和现有 lock/unlock/destroy API 保留。

新增 `.kunitconfig`、`adlak_os_test.c` 和构建入口。测试链接真实驱动，用真实 OS API
分配两把锁并执行 device→SMMU 嵌套，要求 `debug_locks` 前后均为1，不访问 ADLA 硬件。
原有 Python 测试文件未动。

验证与限制：

- arm64 QEMU + KASAN + PROVE_LOCKING：`adlak-os-mutex` 1/1通过，原始输出
  `build/debug-splat-fixes/adla-mutex-kunit-final.log`；VM KUnit `test.log` 与 JSON保留。
- 模块/内建 W=1+C=2，固定 sparse `v0.6.5-rc1-21-g84ec0658`，实际 CHECK 涵盖
  OS 包装、设备/SMMU 调用点及 KUnit；模块完成 MODPOST、`.ko` 和 BTF 链接。
- 既存 vendor GFP 标记类型、format attribute、旧式声明/注释等诊断仍在，不声称
  整个下游驱动零告警。新宏与测试无诊断；新 allocator 延续原 OS 分配接口。
- 修改头文件 kernel-doc 与父提交对照，只有相同的旧 vendor 文件头诊断，新文档无新增。
- 对 format-patch 跑 strict：0 error、1 FILE_PATH_CHANGES 提醒、0 check；人工确认
  既有 MAINTAINERS 的 `F: drivers/misc/adla/` 覆盖两个新增文件。仅忽略这个提醒后
  strict为0/0/0，原始两份日志均保留。未通过添加无用路由条目消除提醒。
- smatch 不可用，未运行。硬件和吞吐结果单独记录，不由 KUnit 代替。

## PD 时序：生产也会经过 Soft_Reset

对照来自同次 `.81` 窗口后正常重启的 `.3`。恢复 JSON 中原始 FUSB302/TCPM 日志已
解码到 `build/debug-splat-fixes/board/{before,after}-{tcpm,fusb302}.log`；
调试尾部仍以 `logs/debug-splat-a81/uart.raw` 为准，软件日志有 UART 交错。
本分支从正式 `.3` 基线至本次修复，没有改 TCPM、FUSB302 或 `include/linux/usb/pd.h`。

| TCPM 事件（启动秒） | 调试 `.81` | 正常恢复后的 `.3` |
|---|---:|---:|
| 设置初始 USB capability=false | 19.986192 | 7.929083 |
| 安排 PORT_RESET_WAIT_OFF，100ms | 19.996765 | 7.936150 |
| 进入 PORT_RESET_WAIT_OFF | 19.996826 | 8.036187 |
| 安排 SNK_UNATTACHED，920ms | 19.996858 | 8.036202 |
| 实际 SNK_UNATTACHED | 20.916956 | 8.956222 |
| 安排 CC debounce，200ms | 20.938199 | 8.972084 |
| 实际 SNK_DEBOUNCED | 21.138324 | 9.172120 |
| SNK_WAIT_CAPABILITIES | 21.140326 | 9.173044 |
| 安排 SNK_SOFT_RESET，310ms | 21.145846 | 9.177669 |
| 实际 Soft_Reset TX | 未采到 | 9.487733 |
| TX complete / Accept RX | 未采到 | 9.495076 / 9.496827 |
| Source_Capabilities RX | 未采到 | 9.501304 |
| Request TX / Accept RX | 未采到 | 9.501571 / 9.514383 |
| PS_RDY / SNK_READY | 未采到 | 9.568869 / 9.568890 |

生产310ms等待实际310.045ms，CC去抖实际200.036ms，920ms阶段实际920.020ms；
Soft_Reset TX至Accept约9.094ms，TX complete至Accept约1.751ms；Request TX至Accept
约12.812ms。这些都不是超出本树响应期限的样本。另一份自动回 `.3` 的生产日志
同样经310ms等待与Soft_Reset成功，并先取5V/1.5A再协商5V/3A，不把固件初始1.5A
当成故障前电源状态。

调试的920ms和200ms阶段分别为920.098ms、200.125ms，没有记录到明显超长；
仅绝对探测晚约12秒，不能推出消息往返超过协议期限。调试100ms阶段的相邻日志
却只差0.061ms，属于需要复核的异常，不能概括成所有定时都变慢。

### 代码如何决定期限及可能的失败链

以下位置均为本次内核树的 `drivers/usb/typec/tcpm/tcpm.c`：

- `:1725` 以 hrtimer REL 安排阶段期限；`:1773` 记录待执行状态；`:6544` 的 work
  在看到 delayed_state 时消费它。100ms异常需要后续确定是否有非定时 work 提前
  消费状态，当前没有 workqueue/调度跟踪证明，不擅自认定竞态根因。
- `:5838` 对接管旧合同、VBUS从未低过的情形先做一次 Soft_Reset；这条恢复策略
  在成功的 `.3` 上也执行。`:6199` 发送后，失败或响应超时可转 hard_reset_state。
- `:1132` 传送过程先等待 TCPC TX complete，再按状态安排发送响应期限；不能从
  probe 的启动秒数算 tSenderResponse。`:6061` 才是实际 Hard_Reset 发送路径。
- 本树 `include/linux/usb/pd.h:666` 的 `PD_T_SENDER_RESPONSE=60ms`（已放宽），
  `:670` 的 `PD_T_SINK_WAIT_CAP=310ms`。生产在TX完成后也会记“待Hard_Reset 60ms”，
  随后收到Accept取消它；待执行行本身不表示已经 Hard_Reset。
- `_tcpm_log():841` 先取 local_clock，再等日志 mutex/分配；日志记录时间不等于
  电气事件边沿。`:6556` 的 delayed日志括号表示请求延迟，不是实测耗时。

若调试负载使 Soft_Reset、TX完成或RX处理超过真实响应期，代码确有进入Hard_Reset
的路径，故值得继续采证；但 `.81` 缺实际TX、Hard_Reset发送/接收、VBUS跌落尾部，
目前只能说机制可能，不能说已证实。也不能区分本机发起与电源端自主Hard_Reset。
冷复位固件 reason0x00/sticky0不补足这些缺口。

下一次若仍复位，需同一时间轴取得Soft_Reset TX/GoodCRC/Accept、Source_Capabilities、
Hard_Reset及CC/VBUS尾部，最好加外部PD/VBUS/RESET观测。当前watchdog sysfs未启用，
没有连续timeleft样本；不靠旧pstore或“没有panic输出”排除看门狗/掉电。
本任务只交时序分析，不修改 PD、供电或看门狗策略，由协调者决定是否另立修复。

## .83 实板与新的 PD 尾部

`.83` 的GNU ID为 `1b57097ac560331fb0f652b8976f7335d84dda2c`，RAM包SHA256为
`cec26cbfcdd430623c9d9ba74faa8bb76f228230a0f16f3c6d910b190d4867dc`。
原始证据 `logs/debug-splat-a83/uart.raw`、`uart-chunks.jsonl`，票
`34af4211ba7242d8b3323a03640b427f` 持有229.43秒；普通FIFO排在H.264窗口后。
暂存前实际可用9,007,861,760字节，payload760,413,210字节另留512MiB；本次没有ENOSPC。

候选段剔除带标签的历史pstore文字后未见BUG/WARNING/KASAN/lockdep告警，
21.224910秒有BCM43752 `.217` 固件成功记录。但没有取得ADLA绑定或`debug_locks`
快照，未就绪即复位，因此不判A通过；指定的eMMC写读与30秒SDIO流量均未运行。
不能用恢复后的 `.3` dmesg代替候选日志。

这次采到更长的实际PD握手：

| `.83` 事件 | 内核日志时戳 |
|---|---:|
| 安排/执行初始100ms阶段 | 21.908439 / 21.909545 |
| 安排/执行310ms能力等待 | 23.077340 / 23.387488 |
| Soft_Reset TX / TX complete | 23.387661 / 23.396242 |
| Accept RX | 23.401238 |
| 返回等待Source_Capabilities，安排310ms | 23.401465 |

Soft_Reset TX至Accept **13.577ms**，complete至Accept **4.996ms**，未超过60ms，
所以“首次Soft_Reset响应超时”不能解释这次复位。后续能力等待的实际到期、
Get_Source_Cap、Hard_Reset或VBUS跌落仍未采到，不能排除后续阶段或电源端行为。
初始标注100ms的阶段再次仅约1.106ms，提前推进现象重复，但无调度跟踪确定原因。

主机UART首条Linux至ROM **25.869779834秒**；Accept日志块至ROM **1.050215834秒**，
ROM UTC `2026-11-05T11:05:41.465104+00:00`，仍为cold_boot。ROM打印晚于实际复位，
不能用这1.05秒直接确定哪个协议期限先到。pstore仍是旧启动内容，未取得 `.83` panic。

首错后没有重试候选，正常重启一次返回 `.3`。`returned-baseline-identity.json`
核对2370文件、GNU ID、服务/UDC通过，`returned-video.log` 的4K接收 **59.566fps**，
新增丢帧/冻结/丢包0；结果标记 `restored=true`、`own_payload_removed=true`。
本窗payload逐文件核验后删除，没有清理其他任务候选。

## 产物复用与后续集成

协调者已核对 release 并清理 hwdecode 下 `.4–.21` 旧候选，报告根分区空闲8.5GB；
本任务未再删除旧候选，不触 `.23/.24/.25`、hdr10、boot-pd、kbase或启动文件。
本次按新指示普通FIFO排队，先验证 `.3` 身份、视频和可用空间。

两个新候选均基于六修复提交53d7db5f377e8，复用同一个任务 O=：
`/home/deepdream/build/debug-splat-fixes/board/prod/kernel`。
先封存生产 `.84`，再在同O=切换配置构建调试 `.83`，不创建新候选O=。
完整配置、归档身份和脚本SHA已在上板前写入结果文件。窗口后轻量删除此O=下
10,768个 `*.o`（逻辑字节4,677,291,704），Image和ADLA `.ko` 摘要前后相同。
被替代 `.81/.82` 的RAM/整包归档随后删除，原始日志、哈希和最终 `.83/.84` 包保留。
未再申请heavy。后续源码重放与未编译边界见[集成记录](2026-11-05-debug-splat-integration.md)。
