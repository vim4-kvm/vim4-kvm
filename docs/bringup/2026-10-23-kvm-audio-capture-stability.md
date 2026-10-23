# 2026-10-23：HDMI 音频与采集稳定性

历史验收决策曾改为≥20轮无未自动恢复失败；物理链路失锁自动恢复照实计数，不算门禁失败。
da19093a…的27轮中24轮完整通过，3轮因旧断言中止但应用自动恢复；后续全量窗口发现EAGAIN残留错误，须修复复验。
最初基线 M0 `47878a0c611d`／One-KVM `382efb70`；后续临时窗口恢复目标改为
[Wave5 隔离正式部署](2026-10-23-wave5-isolation-final.md)：内核 `aa2f875bec2fc`、
build ID `7b8372b894c98ffae12e636a325c86f2b6c85e00`、manager `9b141c5833c0`。
永久停流、需要重启应用、残留ASoC错误、taint或UDC掉线仍属于不可恢复失败。

## 源码与约束

对照 [ENOLINK 基线](2026-10-23-hdmirx-audio-enolink.md) 和
[采集停止复核](2026-10-22-wave5-first-failure-audit.md)。不使用 strace。
板子变更持 Mac board 锁；全部音视频采样同时持 heavy 锁，重型构建仅持 heavy 锁。
不操作 Wi-Fi/P2P、挂起、U-Boot 或不安全 HEVC 尺寸；上板前先完成离线构建。

两仓功能分支均为 `fix/hdmi-capture-stability`，已推送 fork：

| 仓库／独立工作树 | 提交与用途 |
|---|---|
| One-KVM：`build/kvm-stability/One-KVM` | `dce8993d` 有界采集计数；`672b8fd9` 音频重开资格检查 |
| Linux：VM `/home/deepdream/src/linux-7.3-kvm-stability` | `ad343d8f4860a` 诊断；`ede50b1860e70` FDET重试；`35742e7e2d529` 查询修复；`12931e4a42013` 竞态测试；后续提交见下文 |

早期Linux已rebase到aa2f875bec2fc；最新PCM生命周期分支与发布见后续记录。没有切换VM主工作树。
独立 O= `/home/deepdream/build/kernel-kvm-stability-diag`，使用正式 uhd1.config。

## 采集根因与修复

在原 `0,1,1,0` 浏览器序列（640×480、720×400往返）复现稳定输入时停止。
应用增加两个原子累计值统计桥接前后raw帧，结合encoded总数、出帧年龄、管线状态，
每五秒汇总，内存固定。内核保留跨STREAMON的停止计数、errno、原因和帧序号。

四轮原画面断言均过，但第二轮raw／encoded同停于39、79、95帧。
第二诊断窗口停止计数4→6：稳定640×480、PLL/alignment=1，FDET却为高度0或ticks=0xffffff。
RX返回ERANGE，VDIN随即置vb2队列错误；连续两次相同无效值不能被原快照差异检查覆盖。
厂商5.15 `hdmi_rx_wrapper.c` 的ready FSM对不稳定时序先skip_frame，
累计sig_unready_cnt到界限后才关闭输出并进入unready，没有立即永久停流。

仅在动态模式活动租约下把测量ERANGE分类为EAGAIN，VDIN丢帧继续。
RX既有250ms工作器最多延后四次，持续异常仍清ready；真实失锁、模式变化和不支持格式仍拒绝。
actual-C覆盖无效值、不发布结果、下一有效帧及真实变化。证据：logs/kvm-stability/attempt-2/。

首修复12轮仍有三次bus stop：时序查询中间的独立测量遗漏分类，产生错误SOURCE_CHANGE。
第二修复统一三处分类并增加source_changes；实际C竞态注入旧版失败、新版通过且不发布无效时序。
证据：kernel-query-fix-before-test.log、kernel-query-timing-test.log。

## 音频语义与恢复

早期7.3 hw_params在开启PLL前核对AIF/ACR、采样率及格式；失锁ENOLINK、不稳定EAGAIN，
prepare拒绝旧PCM。这保护硬件却让预期源切换经过ASoC错误路径，最新修复改为参数协商与
实时源检查分离，失锁以XRUN通知。厂商5.15 ready FSM同样仅ready后配置音频，失去TMDS即清采样率/关PLL。

One-KVM原recovery在退避前读ready、睡眠后未复查；现改为退避后复查，同格式/generation
跨200ms资格窗口再开PCM。仍可能竞态的ENOLINK/EAGAIN/ERANGE归为AudioSourceChanged，
关闭PCM并继续串行、可取消退避，仅记debug；真实错误保留诊断。最新驱动的XRUN也兼容标准ALSA重准备。

早期旧内核音频恢复证据在audio-loss-restarted-source-2/，正式候选另用check-audio-loss.py复验。
失锁后源端重建AudioQueue；保留失效AudioQueue的旧窗口未过，结论不含该情形或扬声器录音。

## 原严格验收方法

每轮为0,1,1,0四段，不是九类部署测试重复20次。每段15帧资格确认，随后3秒cadence、
fps>5、运动标记、颜色、快照及DMA检查；旧门禁另要求停止/源变化计数与管线重建均为零。
刻意切模式/HPD允许拆管线。新标准保留画面验证，将真实链路失锁且自动恢复单独计数。

## 离线验证与恢复

One-KVM VIM4 Rust 739 passed、2 ignored，Linux部署助手30项通过；
Mac助手因/tmp安全检查失败，改在实际Linux构建器通过，未改测试。
非VIM4 cargo check受既有系统FFmpeg缺少AV_HWDEVICE_TYPE_RKMPP阻塞，未伪造宏。
应用SHA256：`3d3cf2769577c867a3cd2788c7c98c1166ca447facbac117098f0bd64f9825f5`。
rebase后RX／VDIN及Wave5 actual-C全套通过，含音频七档ACR/AIF、无链路零硬件写入、
PLL回收、时序竞态、DMA生命周期和隔离调度竞态；差异checkpatch为0 errors、0 warnings、0 checks。
日志均在logs/kvm-stability：stability-tests-final.log、app-python-tests-linux.log、
kernel-rebased-tests.log、wave5-rebased-tests.log、kernel-release-checkpatch.log。

## 追加复现与厂商链路判定

588f5247…九类曾通过，但最终捕获两条ASoC -67回退；UDC重枚举改为15秒有界等待。

早期Linux 5aaac0e098ece仅将snd_soc_ret的ENOLINK改为debug，保留errno和拒绝配置语义；
这是ASoC范围的日志等级变化，不是过滤验收日志。EIO／EINVAL／ENODEV／ERANGE／EAGAIN仍报error。
actual-C覆盖100次断链及真实错误。8386336e61a7补充限频readiness原因，旧窗口均验证回退和实际HID。

厂商aml_get_tmds_valid_t7检查SQO、时钟匹配和alignment；clock_lock_th=2为2MHz，
高倍率时线缆时钟×4。3ff099187ea5据此替换持续链路的单独APLL位门禁，保留初始PLL锁定。
actual-C覆盖PLL位低但链路有效、SQO/计数/alignment丢失及±2MHz边界，RX/VDIN全过
（kernel-tmds-tests.log）。它未消除真实物理失锁。

## 最新候选27轮与自动恢复验收

Linux分支HEAD 3ff099187ea5bb1b08e0a34dc78a974f604516de，build ID
da19093a7b275128c352c0f92d735620fce168a1；One-KVM仍为672b8fd9。
attempt-9及source-diag-1/2/3累计27轮，24过、3失败；1表示该轮失败，0表示通过：

| 轮次 | 逐轮失败数 |
|---|---|
| 1–10 | 0,1,0,0,0,0,0,0,0,1 |
| 11–20 | 0,0,0,0,0,0,0,0,0,0 |
| 21–27 | 0,0,0,0,0,0,1 |

逐轮路径及原始计数：logs/kvm-stability/latest-candidate-rounds.json，保留旧accepted=false。
上表是旧标准失败数；按用户新标准，1–27轮未自动恢复失败数均为0。
其中24轮完整执行四段，另3轮分别在第1、4、3段旧计数断言中止，不能称27轮全部完整通过。
失败断言之前均已通过运动标记、颜色、fps>5和成功JPEG快照；之后仍在同一应用PID自动恢复。
同一启动的journal中，bus stop→capture started分别为1.014、1.013、1.114秒，
它表示应用管线重开耗时，不是精确的端到端黑屏时长：

| 全局轮次／证据 | bus stop → capture started（UTC） | 应用PID |
|---|---|---|
| 2／attempt-9/kernel-window-journal.log | 11:48:00.535 → 11:48:01.549 | 920 |
| 10／source-diag-1/candidate.log | 11:58:33.898 → 11:58:34.912 | 916 |
| 27／source-diag-3/candidate.log | 12:18:16.834 → 12:18:17.948 | 905 |

source-diag的23个完整轮后服务/UDC/隔离/taint门禁均通过；attempt-9仅有开窗完整health，
三次旧断言中止后未跑该轮独立health（汇总automatic-recovery-audit.json），
候选日志未见ASoC残留错误或需重启应用，不能把回退后的health冒充候选失锁瞬间的采样。
24个完整轮已超过20轮门槛，保留另外三次自动恢复的证据，因此按用户决策复用现有数据。
没有7b8372b8…在同一测试方法下的停流/恢复基线数据；旧f483…诊断不作为该基线对照，不另补跑。
最后一次source-diag-3第7轮，SOURCE_CHANGE 87→89、管线停止并重开一次，VDIN停止计数30→30。
RX采样每秒5次、最多4000次，仅变化时输出：12:18:16.525时5V/HPD均1，
PLL/SQO/alignment同时为0；16.726线缆时钟为0；16.926恢复720×400及28.32MHz。
Mac有效观察器在该失锁区间无显示重配，24.407的回调对应测试退出恢复EDID。
证据：source-diag-3/rx-observations.jsonl、candidate.log、focused-7.log，
以及source-display-events-3b.jsonl；此前两个空回调日志无效，不用于推断源稳定。

这是真实接收链路失锁，不是单独的FDET无效值、VDIN队列错误或应用永久停止。
尚不能区分发送端瞬断、线缆与RX PHY；Mac无重配不等于电气信号未变。
需受控HDMI源／电气观测或厂商5.15同链路对照，不能凭现有证据继续猜寄存器或掩盖失锁。
前一轮因此停止部署并回退：final-restored-health.json确认7b8372b8…、三服务active、
configured、isolated=0、taint=0；source-diag-3/restored-hid.log确认实际键鼠/滚轮。
后续用户明确接受自动恢复标准，授权以本候选正式部署；九类全量及音频失锁仍需针对同一build通过。

## 窗口回退保障

首次正式尝试formal-window通过19模式，H.264在1680×1050的JPEG成功后查到空DMA，
last_stop_error=-67、last_stop_reason=tmds-invalid，旧即时断言失败。退出恢复EDID后管线恢复，
不据此证明原模式恢复；已回退7b8372b8…并通过实际HID，未推进正式分支。
formal-recovery-window保留原画面断言，仅对ENOLINK后的空DMA增加45秒新帧资格等待，
再检查3秒fps>5、运动标记/颜色、JPEG、RX ready和DMA；应用PID/视频SSRC必须不变。
不重启应用、不刷新页面、不改EDID来帮助恢复。原失败日志不覆盖，全部九类重新执行。

第二次formal-recovery-window的19模式、H.264 18段、H.265 16段及4K60通过；
音频首个48k段12:57:28失锁，track/tab分别21/35个坏窗口，12:57:31.765自动恢复，
随后44.1k/48k均零坏窗口。因旧零中断门禁回退，未冒充原采样率持续恢复证明。
第三次formal-qualified-window加入有界声音复验：仅在该段日志同时证实RX失锁/音频自动恢复时，
保留坏窗口并维持采样率、浏览器和PID，再测完整15秒（四次HPD测试为20秒）；
仍用原非零波形/频率/突变阈值和最低窗口数，只允许一次复验，不通过即回退。

第三次九类及四次HPD恢复全过，正常音频track/tab为310/308个窗口、HPD为616/613，bad均0，
未触发额外复验；最终health仍发现ASoC -11两条，因此回退，不能部署da19093a…。
曾构建b076a35c47e7b／d5740fac…日志降级候选，未上板；用户要求改为驱动PCM生命周期修复，
已撤回通用ASoC日志改动，停止重复轮次验收。一次性针对性验证、冒烟和正式多子系统门禁见
[PCM生命周期修复与部署](2026-10-23-kvm-audio-capture-stability-deploy.md)。

沿用f3b0f51冻结helper，本轮未改final-board.py。stop限30秒，失败继续写回并sync；
save先把恢复程序/元数据/rollback.sh存入备份。sudo执行rollback.sh reboot可独立恢复，
verify核对文件/模块/身份，另查隔离和实际HID。离线覆盖stop/reload全超时及无payload回退。
