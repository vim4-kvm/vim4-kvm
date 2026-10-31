# 2026-10-30：npu4三模型字节一致，取消与并行门禁通过

**本轮指定门禁通过。** 三模型101轮全部输出字节一致、task create=0，
平均退化均≤5%；取消0.210ms，同context继续和close/kill回收正常。
逐种故障及profiling后没有复现约104ms退化，视频并行无NPU超时。
这不等于全部厂商接口、真实硬件挂死或长期性能已通过；保页例外仍为**用户已于 2026-10-30 接受**。

## 窗口与身份

GPU收尾记录确认已结束；现场默认5.15、四服务active、UDC configured，锁空闲。
取得本地board/heavy/日志锁及远端双媒体锁，沿用现有编码器互斥，不删除编码器锁文件。
约10:59–11:11 PDT独占，少于30分钟。视频观察40/90秒、等首帧20秒；
单次推理/故障外层10–90秒timeout、分组脚本150–360秒上限，单项均少于10分钟。
不发HID（Mac mini M6）、不测声音、不ptrace、不写PWM/电压、不并行编译、不push。

| 身份 | 值 |
|---|---|
| 原/最终内核 | `5.15.137-vim4kvm-hdrdual6` |
| 原/最终build ID | `4a9b69d62ba7b3a5adeb41b213f7f3e573006165` |
| 候选release | `7.3.0-vim4kvm-npu4+` |
| 内核提交 | `vim4-npu-adla@34f345566a1b9` |
| 候选build ID | `57e1dd72a4287f3982518d1b2e66ed6544ab99d3` |
| bundle SHA256 | `c3d8f2855384c26e5729d9a5baa2c1b26e645a88cead5fd670fc835f41c5e034` |
| 运行时助手源码 | 主仓`1fed075`，五个助手临时安装后按本窗口备份恢复 |

新现场证明生成bundle并stage，仅U-Boot RAM sysboot选择，不改默认、不刷U-Boot。
ADLA probe成功，KMD1.4.0.3，CmaTotal=524288KiB，四服务active。
SDK1.4.0.2与固定Khadas提交模型/输入、probe均沿用[5.15基线](2026-10-30-npu-adla-acceptance.md)，
未重跑5.15推理，也不声称本窗口两内核实时交替配对。
probe SHA为509eee645a022f923c58aa614b14b98009a714edd85df55ca89dd1b08a839aed；
libadla/libnnsdk SHA分别为cd5fc35e273939a50cfe14585d1fb15b60939037a670f679b209c85cdc50a5f8、
10778d0ff47815c039804fb4c814fd064a0eeeb4700cb416a57067e5dac1537a，均与旧基线一致。

## 三模型

每模型101轮、去首轮，input_set＋output_get计时，落盘在计时之外。
本机独立复核505个张量的实际大小/SHA与结果清单及5.15基线一致，输出差异为0。

| 模型 | 5.15均值ms | npu4均值ms | P50 / P99 / max ms | 平均退化 | 字节比较 |
|---|---:|---:|---|---:|---|
| VGG16 | 0.560168 | 0.586605 | 0.582008 / 0.660551 / 0.805803 | +4.720% | 101/101一致 |
| DenseNet CTC | 1.951742 | 1.959342 | 1.950237 / 2.144324 / 2.289200 | +0.389% | 101/101一致 |
| YOLOv8n | 30.133937 | 30.366655 | 30.129113 / 32.824444 / 36.045950 | +0.772% | 三输出303/303一致 |

主测及最终完整dmesg的task create fail均为0，没有fixup拒绝坐标/errno日志。
YOLO第三输出的56664值差异已消除；符合有效缓存长度检查的预期，见内核
`drivers/misc/adla/drv/common/adlak_submit.c:994–1017`及[npu4设计](../npu-adla-npu4.md)。
VGG已接近5%上限，当前结果不应推广为所有环境均无退化。

## 取消、各故障前后与PM

独立tracefs实例仅启用adla_phase，诊断短组与普通101轮性能分开，结束关闭并删除实例。
每项故障后均先测101轮普通DenseNet，再跑5轮trace，profiling置于最后。

| 阶段 | 结果 | 后续100个暖样本均值 / P99 / max ms |
|---|---|---|
| 无故障对照 | 正常，101份输出一致 | 1.932952 / 2.027071 / 2.153282 |
| CANCEL | 同fd3/net0，内核rc=0，0.210420ms；WAIT errno125 ECANCELED | 1.972872 / 2.607788 / 2.726207 |
| WAIT timeout=0 | WAIT errno110 ETIMEDOUT；无外层timeout | 2.029970 / 2.195282 / 2.292242 |
| SIGKILL/close | 独立探针INVOKE后退出137，随后新context正常 | 2.014805 / 2.298034 / 2.546162 |
| profiling | DenseNet三轮正确，1662µs、644320bytes，destroy成功 | 1.950835 / 2.214657 / 2.342451 |

cancel/WAIT故障各在同一context继续4次INVOKE，8份成功输出全部一致，destroy rc/status=0。
被取消/超时的首轮各有1份错误输出，属于失败请求，不能消费；SDK仍返回有限输出/退出0，
必须依据ioctl errno和逐张量合同判断，不把失败首轮算正常推理。
所有正常恢复组的输出全部一致，无Failed to free buffer、Not support status或recovery failed日志。

trace确认cancel不是只删pending：先submit，irq_wait返回-125，然后reset成功6042ns，
其后4次正常执行；WAIT超时reset为5834ns，kill/close的reset为6084ns。
正常/故障后的submit最大约219µs、IRQ等待最大约1554µs、完成解析最大约1.63µs；
profiling完成解析最大2.292µs。各phase读回时钟均799999987Hz。
ADLA IRQ从初始505推进到profiling后的1042，worker的schedstat/status快照完整保留。
以上支持取消分流与唤醒修复有效，但不能唯一分解npu3历史104ms的全部成因。

初始、每种故障后、profiling后及收尾iova_free=2142228480、iova_max=2147483648，
CmaFree=505208KiB；收尾模块引用0，无探针。活动约800MHz→空闲0Hz、runtime suspended，
各次新请求可再唤醒。可见资源无净泄漏，不等于逐页DMA/PTE审计。
ATTACH buf_type=0与两次负向PROFILE_CFG退出0；真实复位失败、GET_STAT专项及整机挂起未测。

## HDMI＋Wave5并行

复用One-KVM 4K NV12→H264/Wave5；独立recvonly WebRTC页，不加载产品UI，
无HID通道/音频transceiver，不另开编码器、不主动操作源端画面。

| 接收窗口 | 秒 | 解码增量 | fps | 丢帧 / 丢包 / 冻结增量 |
|---|---:|---:|---:|---|
| NPU关闭初始基线 | 39.162 | 2349 | 59.9816 | 0 / 0 / 0 |
| 并行会话NPU开启前 | 73.227 | 4395 | 60.0188 | 0 / 0 / 0 |
| 完整重叠组内 | 13.037 | 782 | 59.9831 | 0 / 0 / 0 |

首次接收统计已有1帧startup drop，后续未增加；不把增量0写成绝对0。
采集/编码日志raw/pushed/encoded同步推进；18:06:49–18:06:59 UTC由4499至5100，
无Wave5帧缓冲-ENOMEM、Failed to process frame或编码输出停滞。

10组各1000轮全部完成、退出0，10000份输出均与DenseNet基线字节一致。
按时间戳预先规则只取完整落入接收统计窗口的组0–5：6000轮、各组去首轮，
5994样本均值2.013532ms，P50/P99/max=2.005238/2.183782/2.797667ms。
相对本轮单独DenseNet均值增加2.766%，相对5.15基线增加3.166%。
组6跨越接收末点、组7–9在窗口外，保留全部数据但不纳入并行统计，无超时/失败挑样本。
本窗口未复现npu3的持续104ms及15秒超时，仍不替代长期/运动场景资格。

## 工具修正、回退与证据

首版诊断编排以root启动SDK，网络创建失败、没有有效phase；改为root仅管trace，
SDK按基线用户khadas运行，原失败日志保留，不算驱动故障或性能样本。
并行首版误传1001轮，超出probe的1000上限，立即退出2、未执行推理；
修正测试参数后使用全新目录，未在板上改驱动。两次工具无效运行均不混入统计。
归档完成前曾提前下载一次，解包报截断，完成后重新下载并通过全部SHA复核。
回退脚本沿用旧路径覆盖了本机r8的回退UART副本，现已归档本次UART至r10；
r8原始/最终JSON证明和候选产物未修改，本次最终状态以r10新证明核对。

普通reboot回5.15；原始/最终证明显示12文件SHA及uid/gid/mode一致，默认build ID不变。
one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget均active，UDC configured，
无残留探针；约11:11 PDT释放本地/远端锁与串口，不再访问板子。
本机证据`build/npu-board-20261030-r10/`，板上`/var/tmp/vim4-npu-accept-20261030-r10/`。
含original/stage/candidate/final证明、UART、505张量、phases-khadas的trace/计数/全部输出、
10000份并行张量、parallel1000-result.json、summary.json、视频接收及服务日志、完整dmesg。
新窗口脚本、参数和本机分析器随忽略目录保留，未改正式部署锁。
主仓unittest：308项、7跳过，OK，日志为本机证据目录unittest.log。
本轮只提交NPU记录、索引和状态，不混入并行GPU工具改动。
