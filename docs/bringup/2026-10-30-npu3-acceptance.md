# 2026-10-30：npu3 上板，视频恢复、YOLO缓存fixup合同与恢复后延迟仍失败

**整体未通过。** VGG16/DenseNet完整输出与均值门槛通过；YOLO第三段仍被拒绝，
本次已取得具体errno、task坐标及SDK参数。Wave5的NPU关闭基线恢复到4K60；
并行时视频推进正常，但NPU探针超时，且故障测试后独立NPU也变慢，不能宣布并行追平。
本轮只取证，不在板上改驱动。交接时已回默认5.15、恢复助手并释放全部锁。

## 窗口、版本与证据

2026-10-30约09:57–10:19 PDT，独占约22分钟；开始确认5.15、服务正常、锁空闲。
取得board/heavy/日志锁、远端媒体锁及串口，沿用现有编码器互斥机制；未删除锁文件。
每项有进程timeout且少于10分钟。无HID、音频测试、视频ptrace、PWM/电压写入或并行编译。
Mac mini M6未接受任何键鼠操作。交接后不再访问板子，供紧接的GPU窗口独占。

| 项目 | 身份 |
|---|---|
| 原/最终release | `5.15.137-vim4kvm-hdrdual6` |
| 原/最终build ID | `4a9b69d62ba7b3a5adeb41b213f7f3e573006165` |
| 候选release | `7.3.0-vim4kvm-npu3+` |
| 候选build ID | `3a822b8a9f47a8f1a8a74016e5128d9d14d104f5` |
| 内核提交 | `vim4-npu-adla@bc8324ccb92927013e5a69cfc24d658309118925` |
| bundle SHA256 | `f4a01cea3bdd6de76a4f8dfe0e81cc439abb3cf5a20a585e0760f57b5470530e` |
| probe SHA256 | `509eee645a022f923c58aa614b14b98009a714edd85df55ca89dd1b08a839aed` |

SDK 1.4.0.2、模型、输入及probe与[5.15基线](2026-10-30-npu-adla-acceptance.md)一致，
未重跑5.15推理。五个匹配运行时助手备份后临时安装，确认启动器支持npu3，
再生成现场证明、prepare/stage；仅U-Boot RAM sysboot选择候选，不刷U-Boot、不改默认项。
完整载荷含2338个匹配模块，CmaTotal=524288 KiB，UART为512 MiB at 0xbf000000。

原始证据在本机`build/npu-board-20261030-r8/`及
板上`/var/tmp/vim4-npu-accept-20261030-r8/`；本机已下载全部505份候选张量并核对SHA。
关键文件：original/stage/candidate/final.json、summary.json、after-models.log、
final-dmesg.log、video-service.log、UART、三个candidate目录、yolo-observe、fault-*、
resources-*、video-baseline/parallel.log及parallel.log。最终dmesg环形缓冲已覆盖早期日志，
任务失败计数使用完整保留的after-models.log，不能拿最终日志的零匹配冒充零失败。

## 三模型：101轮，去首轮

计时端点为input_set＋output_get，张量落盘在计时区间之外。复用历史5.15基线，
不是本窗口两内核交替配对；505份文件均验证传输完整，再与基线逐字节比较。

| 模型 | 5.15均值ms | npu3均值ms | P50 / P99 / max ms | 均值退化 | 完整输出 |
|---|---:|---:|---|---:|---|
| VGG16 | 0.560168 | 0.551826 | 0.547424 / 0.584758 / 0.717593 | -1.489% | 101/101相同 |
| DenseNet CTC | 1.951742 | 1.921732 | 1.917442 / 2.061528 / 2.150779 | -1.538% | 101/101相同 |
| YOLOv8n | 30.133937 | 31.703793 | 31.410670 / 35.980148 / 36.837201 | +5.210% | 第三张量101/101不同 |

YOLO前两个张量共202份相同；第三张量每轮56664/57600个float32不同，
max abs=29.17729187、mean abs=9.50198487，候选均为-17.00094223。
第三段没有执行，计时不代表等量工作，即使均值门槛通过也不能判性能追平。
主测量记录**101次task create fail**，零错误门槛失败。

### YOLO：确认缓存fixup复用被误拒绝

限频内核诊断为`invoke task 380: fixup range 0+1 exceeds 0`。
失败后仅追加一次独立参数观察，不修改驱动、不重跑挑选性能样本：

```text
REGISTER fd=3 net=0 tasks=383 config=178180 compressed=0 cmq=1
INVOKE fd=3 net=0 invoke=1 start=1 end=323 fixups=2
INVOKE fd=3 net=0 invoke=2 start=325 end=356 fixups=0
IOCTL_ERROR fd=3 nr=5 errno=22
INVOKE_REJECT fd=3 net=0 invoke=-1 start=358 end=381 fixups=0
```

注册任务快照`yolo-observe/registered-fd-3.tasks.bin`中，task 380/381的
addr_fixup_offset/count分别为0/1、1/1，config_offset为177932/178056、size均124。
本模型未压缩，不能再用压缩命令格式解释这次拒绝。
以下源码行号均相对上述内核提交的`drivers/misc/adla/`：
`drv/common/adlak_submit.c:948–979`只在本次count非零时更新模型缓存及缓存count，
count=0保留此前两个fixup；`:994–1000`却按本次count=0检查非空任务区间，返回EINVAL。
`:1232`在创建失败后记录错误并退出，未入执行队列。错误输出与task create失败因此同源：
**SDK使用缓存复用合同，适配检查误用当前提交数量**。后续离线应按有效缓存边界检查，
增加“先提交两个fixup、后提交零个而任务仍引用缓存”回归；仍须重新上板确认第三段执行。
独立观察仅对NPU探针使用shim；主性能测量和视频进程均未加载shim。

## 同context取消、超时、close与PM

| 项目 | 观察结果 |
|---|---|
| CANCEL | 同fd=3/net=0首轮INVOKE后取消，rc=0，5190.013 ms；WAIT errno=125 ECANCELED |
| WAIT timeout=0 | 返回errno=110 ETIMEDOUT，首轮5201.418 ms；未触达外层20秒timeout |
| 同context继续 | 两种故障后各4次INVOKE均正常，完整DenseNet输出字节一致；destroy rc/status=0 |
| SIGKILL/close | 仅杀独立探针，退出137；随后新context可正常执行 |
| 后续新context | 三种故障后各3轮，9份DenseNet输出均一致，无释放失败日志 |
| 可见资源 | 故障前、各次后及收尾iova_free均2142228480，iova_max=2147483648；CmaFree均505208 KiB |
| 收尾 | 无探针进程，ADLA模块引用0，sysfs为clock gating and suspended |

正常取消/超时的错误传递、有界返回和可见资源回收改善；**快速唤醒仍有缺陷**。
`drv/common/adlak_submit.c:1565`为非可中断wait_event_timeout，而
`drv/port/os/linux/adlak_os.c:605–610`通知使用wake_up_interruptible；
这与等待约完整5秒、到期才重新检查已排空条件的现象一致，需离线修复和回归。
资源计数不等于逐页DMA/PTE审计；未强制真实硬件挂死、软复位失败或迟到close回收分支。
保页例外仍为**用户已于 2026-10-30 接受**，本次未触发故障锁定状态。
最终PM可挂起，但故障后性能异常，不能把资源归零解释为所有运行状态已恢复。

补充ATTACH buf_type=0及两次负向PROFILE_CFG均退出0。正向profiling三轮VGG输出正确，
SDK返回24 µs、3298400 bytes、destroy成功，但暖轮均值104.334 ms（含207.783 ms异常轮）；
接口可调用，时序不能判通过，须与下述故障后延迟一并分析。

## HDMI采集＋Wave5并行

复用One-KVM的4K NV12→H264/Wave5路径；独立recvonly视频WebRTC接收页，
不加载产品UI、不建HID通道或音频transceiver、不另开编码器。现有画面未人为制造运动。
接收端统计framesDecoded、framesDropped、packetsLost和freezeCount；
采集/编码/解码帧持续推进，日志无npu2的帧缓冲-ENOMEM或Failed to process frame。
并行边界附近17:07:54–17:08:09 UTC，raw/pushed/encoded同步由3599推进到4500，
共901帧；没有编码输出停滞或新增编码失败日志。

| 接收窗口 | 秒 | 解码增量 | fps | 丢帧 / 丢包 / 冻结增量 |
|---|---:|---:|---:|---|
| 首次NPU关闭基线 | 39.166 | 2351 | 60.0266 | 0 / 0 / 0 |
| 第二会话NPU开启前 | 60.244 | 3620 | 60.0890 | 0 / 0 / 0 |
| 与实际NPU运行重叠 | 14.052 | 843 | 59.9915 | 0 / 0 / 0 |

NPU计划15组×1000轮DenseNet，首组运行到141轮便触达**15秒外层timeout**，未重试，
没有完整parallel-result.json。已有141份输出相同；去首轮的140个**不完整样本**
均值106.004 ms、P50/P99/max=107.581/107.743/107.846 ms，不能当成完成1000轮的结果。
随后请求停止视频（clients=0、fps=0）再测101轮，输出仍正确，
去首轮均值104.200 ms、P50/P99/max=103.561/107.811/107.813 ms。
停止接口后status的state仍写streaming，不据此宣称整个物理管线完全停止。
独立对照仍慢且此前profiling已异常，**不能把约100 ms延迟简单归因于视频竞争**。
final-dmesg记录取消期间的`Not support status[0x00000000]`与大量idle检查警告，
先于并行窗口；后续需分析复位/IRQ/profiling状态，而不是忽略该顺序只比较均值。
视频基线恢复、接收帧推进通过；NPU并行完成性和恢复后性能未通过。

## 回退与后续

普通reboot回5.15；五个助手按**本窗口**备份恢复。original.json与final.json证明
12文件SHA及uid/gid/mode全等，包括启动文件、登记文件和助手；默认内核build ID不变。
交接时one-kvm、vim4-manager、vim4-kvm-hdmi、vim4-kvm-gadget均active，
UDC `fdd00000.crgudc2`为configured，无残留探针；10:19 PDT释放本地/远端锁及串口。
未push、未修改正式内核锁，不遗留候选默认选择。GPU后续窗口不属于本文状态核验范围。

下一轮先离线修复缓存fixup合同、取消等待通知类型，再查故障/profiling后的IRQ与延迟状态；
候选重建并通过宿主回归后，复用5.15基线刷新现场证明，按相同≤30分钟顺序复验。
YOLO须101轮全字节一致且task create=0；恢复须无释放失败且延迟回归正常；
并行须完整完成预定样本，报告全窗口视频计数与NPU尾延迟。

记录与状态更新后的主仓离线unittest：308项、7项跳过，结果OK；
日志为本机证据目录的unittest.log。本轮无内核改动、无重新构建。
