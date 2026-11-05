# 2026-11-05：PD FIFO 移植与调试、生产候选验证

结论：`.92` 调试候选首次启动仍 cold_boot，A失败，停止后续三次启动。
生产 `.93` 首包因构建器保留旧生成配置而无效，已修复并重建；正确生产包已成功就绪，
一次测试被脚本误判既有 WEXT 弃用警告而提前结束。补测600秒均值326.97 Mbit/s，
比369.55基线低11.52%，性能未通过，未改回硬IRQ完成；所有窗口最终恢复`.3`与视频。
按协调者的合入条件，当前 `pd-fifo` 不能随集成分支合入；不因生产启动成功改写A失败。

前序：[状态机、拓扑与频率审计](2026-11-05-tcpm-coldboot-audit.md)、
[集成基线](2026-11-05-debug-splat-integration.md)。以下时间均为UTC。

## 两封上游邮件与提交

在原VM任务工作树新建内核 `pd-fifo`，基于协调者指定的
`fd41fb5950b9da1fb336ce00d5137d27ee9755fa`，只改 `drivers/usb/typec/tcpm/fusb302.c`：

| 提交 | 根因、修法与来源 |
| --- | --- |
| `d76280411565d9d5bbba1979639703a7e88128be` | 中断位不是FIFO报文计数，单帧消费可落后于队列；增加按RX_EMPTY排空的有界循环。[Drain the RX FIFO](https://lore.kernel.org/r/20261102-fusb302-drain-rxfifo-v1-1-bd9b232ab345@flipper.net)。最终HEAD函数在fusb302.c:1503。 |
| `bbe16d470a0c1e3c591eeb1a5c1d40a03985c5f8` | 邮件报告芯片不确认type17却仍入队；不把这种未确认帧交TCPM发出不合时宜响应。[Drop unacknowledged Get_Source_Cap_Extended](https://lore.kernel.org/r/20261102-fusb302-getsourcecap-v1-1-26b5bfea4b2b@flipper.net)。条件在最终HEAD:1476。 |

原作者都是Alexey Charkov，保留From、日期、正文与原Signed-off-by；增加Link、本项目
既定提交者Signed-off-by和“v1尚未合入上游”说明。第二封只去冗余条件括号以通过strict，
正文注明等价风格调整。没有已合入git提交可cherry-pick，使用git am，不自写另一套。
原 `debug-splat-fixes` 与 `debug-splat-fixes-v2` 分支均保留，未改其他工作树。

此次从lore的`/t.mbox.gz`取得完整线程，而非搜索摘要；原始单邮件SHA256：

- drain：`fef4d7e53213839602c719718c14bb96b8d2934a9ae4685968b4b15736dfdc49`。
- getsourcecap：`67d9dd20d10c8ee5473a21a535c0344d8b444c3a273fe5c0ea03fa22b105e041`。

归档含邮件头、正文、diff和作者回复。上游树快照与未合入状态见前序审计。本轮未对外
发信或push，未改TCPM状态机、超时、DT、PDO、供电角色，也未改调试配置或关闭检查。

## 离线检查与构建

两提交format-patch分别strict **0 errors / 0 warnings / 0 checks**（59/19行）。
逐提交、逐模块/内建的最小arm64配置均实际生成Image和模块，W=1+C=2检查FUSB302，
固定sparse `v0.6.5-rc1-21-g84ec0658`，四组exit0，修改文件无诊断。
既存tcpm.c:1706的`__le16`诊断、vDSO诊断，以及首组最小配置的arm64重复初始化警告保留；
不是全树零警告。首次借用旧符号表的模块链接因mutex导出名不匹配失败，未算通过；
改成重建真实核心及符号表后重跑，原失败日志保留。smatch未安装。

遵照协调者要求，不写伪造I2C的KUnit；本轮FUSB验证使用实板启动与SDIO流量。
主仓新Python回归只验证构建器配置门禁，不模拟硬件。

主仓 `988212f` 从kunit-migration的`931bdf2c`原样引入build-integration.py；其他配方依赖
与本工作树相同。主仓 `6609f147dd77` 修复下述生成配置问题。
集成构建者当时仍使用自己的O=，所以沿用本任务唯一目录
`/home/deepdream/build/debug-splat-fixes/board/prod/kernel`，所有构建持heavy票。
封包后构建器删除该任务的对象文件，板窗后检查没有剩余`*.o`。

| 候选 | GNU build ID | 身份/生效配置 |
| --- | --- | --- |
| `.92` debug | `da21aec5c6e6d6d530724efb7260f6a3b106128e` | debug配置SHA `16e40afc…`；生效配置正确。 |
| 首个标称production `.93` | `79353cfb3e170ac168c5f867901ae5364dea228e` | 无效：所附config为生产，实际编译仍是debug，禁止作为生产结果。 |
| 正确production `.93` | `aa7e2a197461461711988b2be115516b1dda442f` | 生产config SHA `7be7563e…`，生效值全部匹配，vmlinux无kasan_report。 |

正确两包均2341模块、2354模块文件、2358 RAM文件；检查每个模块的vermagic/GNU ID/BTF、
所有文件SHA、Image GNU note、static init和完整恢复清单。正确生产包还复核生成配置证据。
归档SHA分别为：

- `.92`：`75c24c2d98045e1c48f159fa616079306929ec998f5b047314ead4693dca6add`。
- 正确`.93`：`c173ca31b1d94993abe565e1c425212b874087fbd948707c084a0f1b3ee50367`。

旧无效`.93`和日志完整留存，正确包另放`candidates-corrected/production`及本地
`production-corrected/`，没有覆盖旧包。该release未验收、未安装为默认；以GNU ID和SHA
辨别两套候选，不凭相同release混用模块。生产配置文件始终未改。

## 生成配置缺陷及修复

`shutil.copy2`保留kernel.config旧mtime。复用O=从debug切production时，make clean不删除
生成头；olddefconfig在无选项变化时不重写.config，较新的auto.conf/autoconf.h遂保持debug。
首次`.93`的.config看起来正确，实际仍有KASAN/PROVE_LOCKING/DMA_API_DEBUG；Image为
90761728字节，日志编译mm/kasan对象，UART也打印DMA debugging enabled。

原独立RAM复读只能证明档案、身份和所附配置完整，不能证明编译器使用了该配置；
此前“生产全量构建通过/生产也复位”的结论撤回。生成快照与`.92`完整debug配置匹配。
旧`.90`是先production再debug的构建顺序；其Image为48282112、生产日志无mm/kasan编译，
本轮未据此判它无效，也未改它的构建树。

`6609f147dd77`改用copyfile刷新mtime、显式syncconfig，并在编译前后逐项比较.config启用值
与auto.conf，处理禁用项省略和字符串外层引号；保存auto.conf/autoconf.h及SHA到候选身份。
两项新回归覆盖旧debug配置必须拒绝、有效生成配置可接受，另带原配方的三项配置检查。
实际旧快照被新门禁拒绝；正确生产重建通过全量、配置与二进制检查。

## A：调试首次启动仍复位

票 `1bc1693a95de438b80cb5d62daf9bab0`，实际149.851489秒。
13:27:34.390894进入`.92` Linux，Wi-Fi固件在20.012253秒初始化；13:27:58.131162回ROM，
主机monotonic差 **23.740267917秒**，随后U-Boot cold_boot。无panic或候选段新
lockdep/KASAN/DMA-API告警；只观察到调试设施启动的正常信息。

在SSH/服务ready前停止，未取得运行时GNU note、lockdep_stats、ADLA绑定快照，
未跑指定eMMC直接写读、SDIO流量或十分钟观察。result中的boots为空仅表示没有完成ready
记录，不能解释为没启动候选。UART和已验包证明实际启动了一次`.92`。

首次失败即停，未做后续三次启动。协调者已同意三次采用reboot回U-Boot重新RAM加载，
并注明未主动断电；但该条件在本轮未触发。没有通过关闭PD、改延迟或其他变量继续试。
标准集成init不含此前私有SPLAT_DIAG子进程，仍发生复位。

## B：生产配置与脚本误判的边界

旧无效`.93`票实际154.342168秒，13:36:15.110405进入Linux，13:36:40.370201回ROM，
差25.259796542秒；它实为debug，不能放入生产复位样本或当作B结果，600秒未运行。

正确`.93`首次B已SSH/服务ready，运行态GNU ID实测aa7e…匹配，但任务脚本用
case-insensitive WARNING误报启动6.108573秒的既有消息：
`warning: iwconfig uses wireless extensions … use nl80211`。
源码为net/wireless/wext-core.c:642的pr_warn_once，没有WARN()堆栈；历史`.3`恢复UART
也有此条。本次不是新增lockdep/KASAN/DMA故障，脚本仍按原规则停止并恢复，未测吞吐。
该票115.020341秒，完整旧脚本与错误收据保留。

只修任务脚本的splat分类：uppercase WARNING的WARN()仍拦截，BUG/KASAN/lockdep/DMA-API
规则全部保留；弃用warning原文仍在dmesg，并单列non_splat_warning_lines，不说它消失。
用原始r32核对五条PWM/DMA/KASAN特征、r33b Invalid wait及`.81`ADLA递归告警仍命中。
不为了未来Wi-Fi 7改现有服务或驱动。

补测使用同一正确包和已保存5GHz配置，Mac 192.168.50.239:5217，板端wlan0单TCP反向
接收，无tracing；实际600.000517秒、600个一秒区间，GNU ID运行时匹配，期间没有复位
或新目标splat。原WEXT弃用warning仍出现并保留。TCPM在启动6.047486秒达到SNK_READY，
缓存合同为5V/3A；这是协商值，不是电流实测。

| 接收端指标 Mbit/s | 旧基线 | 本次 |
| --- | --- | --- |
| 总均值 | 369.55 | 326.968434 |
| p10 | 337.64 | 281.018653 |
| p50 | 372.24 | 332.398097 |
| p90 | 398.46 | 368.049079 |

均值下降11.522545%，已报告协调者，未改回硬IRQ。连接5200 MHz、信号-37 dBm；
sender累计6745次重传，原始JSON保留。只能报告本组相对历史基线的下降，不能单凭它
将差异全部归因于MMC或PD。没有追加对照实验或调参。

## 恢复、结论与后续判据

每次已执行窗口都正常回`.3`，核2370证明文件、GNU ID
`e595ad243d663f6c33b92678a4de6e0b78ec16d5`、服务和UDC，并实收4K视频：

| 窗口 | 恢复FPS | 解码帧增量 |
| --- | --- | --- |
| A | 59.774823 | 299 |
| 旧无效B | 59.577798 | 298 |
| 正确B被脚本中止 | 59.595463 | 298 |
| 补测B最终恢复 | 59.988834 | 300 |

各次新增丢帧/冻结/丢包均0，私有候选与本次专用固件副本经身份/全文件校验后删除。
补测收尾有两处错误，不能以原result缺restored字段宣称恢复成功：轮询保留190秒而
启动测量只预留120秒，导致仍有足够恢复时间时跳过SSH探测；紧急短票已正常重启`.3`，
但候选诊断文件candidate-pd-forensics.json被工具当成清理计划，清理在视频之前失败。
随后只补清理与视频，未再次重启，最终2370文件/GNU ID/视频均通过。
预算逻辑已修为一致保留并至少探测一次、恢复不完整必须报错；tools/board-window只枚举
record_candidate生成的40/64位身份文件，并用实际文件回归防止再次误读诊断JSON。
完整失败收据与最后final-restoration-result.json分开保留，没有回写为首次成功。
累计实际占板1148.812728秒（19.15分钟），含补恢复；所有票已释放，没有继续上板。
两次cold之后无对应`.92/.93`panic记录，pstore仍为历史`.3/uhd6`。没有主动切VBUS，
也没有实际Hard_Reset/VBUS/RESET波形闭环，不能仅凭cold_boot确定PD掉电或watchdog。

两个上游补丁未使调试候选稳定；不据此排除所有PD路径，也不继续猜改第三个驱动方案。
本轮不合入、不push；协调者按A失败条件只考虑integration-73，构建器修复另行审阅。
MMC吞吐明显下降，未宣称性能验收通过；debug_locks与真实eMMC/SDIO调试门禁未完成，
不能拿早期无splat替代。后续调试仍需零目标告警、debug_locks持续1、ADLA/Wi-Fi与真实I/O路径；
复位专项需要实际协议发送/超时执行与外部CC/VBUS/RESET顺序，另经协调者安排。

完整命令、归档和失败日志在本工作树`build/debug-splat-fixes/pd-fifo/`；
UART/身份/恢复证据在`logs/pd-fifo-92`、`pd-fifo-93`、`pd-fifo-93-corrected`及`pd-fifo-93-throughput`；
完整结果追加`~/.local/state/herdr-workers/debug-splat-fixes.result.md`。
