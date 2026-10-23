# 2026-10-23：HDMI 音频与采集稳定性

状态：未通过20轮零失败，未正式部署。最新候选27轮中3轮失败，已恢复隔离基线及实际HID。
最初基线 M0 `47878a0c611d`／One-KVM `382efb70`；后续临时窗口恢复目标改为
[Wave5 隔离正式部署](2026-10-23-wave5-isolation-final.md)：内核 `aa2f875bec2fc`、
build ID `7b8372b894c98ffae12e636a325c86f2b6c85e00`、manager `9b141c5833c0`。
功能分支已推送，未推进部署分支或源码锁。音频四次失锁恢复通过仅指早期内核上的应用修复。

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

Linux 已 rebase 到 `aa2f875bec2fc`，没有切换 VM 主工作树。
独立 O= `/home/deepdream/build/kernel-kvm-stability-diag`，使用正式 uhd1.config。

## 采集根因与修复

在原 `0,1,1,0` 浏览器序列（640×480、720×400往返）复现稳定输入时停止。
应用增加两个原子累计值统计桥接前后raw帧，结合encoded总数、出帧年龄、管线状态，
每五秒汇总，内存固定。内核保留跨STREAMON的停止计数、errno、原因和帧序号。

四轮原画面断言均过，但第二轮raw／encoded同停于39、79、95帧；200ms RX采样未见
失锁不足以排除瞬态。第二诊断窗口在稳定640×480段复现停止计数4→6，捕获：

```text
[78.935039] capture check: measurement error=-34 width=640 height=480 ticks=16777215 lease=640x480/2780036 pll=1 align=1
[82.137652] capture check: measurement error=-34 width=640 height=0 ticks=16777215 lease=640x480/2779994 pll=1 align=1
raw=(59,59) encoded=59 last_frame_ms=15 signal=640x480/60
raw=(93,93) encoded=93 last_frame_ms=15 signal=640x480/60
```

RX无效测量返回ERANGE，VDIN随即置vb2队列错误；不是编码器单独停止。
0xffffff连续两次可能相同，原“两个快照不同才EAGAIN”不能覆盖。
厂商5.15 `hdmi_rx_wrapper.c` 的ready FSM对不稳定时序先skip_frame，
累计sig_unready_cnt到界限后才关闭输出并进入unready，没有立即永久停流。

修复仅将动态模式且活动租约下的测量ERANGE分类为EAGAIN，VDIN标错丢帧并继续。
RX既有250ms工作器最多延后四次，持续异常仍清ready并恢复；真实失锁、有效模式变化、
不支持色彩和隔行输入仍拒绝，非活动租约下无效测量仍ERANGE。
actual-C测试覆盖饱和值、零高度、不发布无效结果、下一有效帧、失锁和有效模式变化。
证据：`logs/kvm-stability/attempt-2/`，该轮失败后恢复旧基线并通过实际HID。

首修复12轮停止计数未增，但日志发现三次bus stop／重建，不算零失败。
时序查询在前后状态检查之间还有独立FDET测量，
漏掉的中间ERANGE可产生错误SOURCE_CHANGE，使GStreamer重协商失败且不增加vb2停止计数。
第二修复统一三处分类并新增source_changes计数；查询中间一致饱和值注入在旧修复失败、
新修复通过，且不发布时序／周期。证据：`kernel-query-fix-before-test.log`、
`kernel-query-timing-test.log`。

## 音频语义与恢复

7.3 `t7_hdmirx_audio_hw_params_locked()` 在开启PLL／FRHDMIRX前核对AIF/ACR、
原生采样率及资格格式；失锁ENOLINK、不稳定快照EAGAIN，prepare也拒绝旧PCM。
厂商5.15 ready FSM同样仅在信号ready后配置音频／PLL，失去TMDS则清采样率并关PLL。
厂商TDM hw_params设置本地时钟，不等价于等待输入源。保留拒绝语义；持audio_lock
阻塞会阻碍资格确认／重配，不应在hw_params内等待锁定。

One-KVM原recovery退避前读取ready，睡眠后未复查。修复在退避后复查，并要求同一格式／
generation跨过200ms资格窗口后再打开PCM。读取控件与hw_params仍有竞态，其中
ENOLINK/EAGAIN/ERANGE归为AudioSourceChanged，关闭PCM后继续已有串行、可取消的
退避恢复。源变化只记debug，真实设备／配置错误保留诊断。
明确失锁时直接arecord仍应失败。

实测 `audio-loss-restarted-source-2/`：同一浏览器连接、同一候选应用进程，四次HPD拉低5秒，
during_loss均link_ready=0；恢复后源端重建440Hz AudioQueue，按48k／44.1k／32k／48k
设置并实读，核对RX audio_rate／audio_pcm／link_ready。每段20秒，沿用原5秒稳定期
及全部连续性阈值：track-direct 608个、tab-direct 607个100ms窗口，bad=0；
四次API streaming=true、error=null，每次一次恢复尝试。内核journal为-- No entries --：

```text
AUDIO_LOSS_CONTINUITY_PASS
AUDIO_RESTORED_48000
AUDIO_NO_RESIDUAL_ERRORS_PASS
```

最初保留失效AudioQueue的窗口未过；结论不含该情形或物理扬声器录音。
正式候选音频复验使用`check-audio-loss.py`，在已持双锁的正式窗口内执行。

## 严格验收方法

保留原序列的帧推进、颜色、同帧标记、快照、DMA、fps>5和cadence断言。
每段完成15帧资格确认后，3秒cadence／快照采样前后要求stream_stops与source_changes
均不增加；用journal cursor检查该段应用started／bus stop／timeout为零，不依赖两端时钟。
刻意切模式／HPD区间允许正常拆管线。20轮指历史故障的四段浏览器序列，不是九类部署测试重复20次。

```sh
python3 -u build/kvm-stability/query-acceptance.py > logs/kvm-stability/query-acceptance-resumed.log 2>&1
# 计划为5轮 → 九类全量回归 → 3轮，再三个各4轮窗口；失败即回退。
# 每窗口持heavy/board双锁，结束恢复7b8372b8…并验证实际HID，组间释放锁。
```

九类为19个HDMI模式、H.264、H.265安全尺寸正反向采样、4K60、音频48k→44.1k→48k连续性、
实际HID、虚拟介质主机传输、受限GPU、manager浏览器。首候选全过证据：
`attempt-3/kernel-window/regression-results.json`，产物在`attempt-3/full-regression/`。
历史结果不代替rebase后验收。

## 离线验证与恢复

One-KVM VIM4 Rust 739 passed、2 ignored，Linux部署助手30项通过；
Mac助手因/tmp安全检查失败，改在实际Linux构建器通过，未改测试。
非VIM4 cargo check受既有系统FFmpeg缺少AV_HWDEVICE_TYPE_RKMPP阻塞，未伪造宏。
应用SHA256：`3d3cf2769577c867a3cd2788c7c98c1166ca447facbac117098f0bd64f9825f5`。
rebase后RX／VDIN及Wave5 actual-C全套通过，含音频七档ACR/AIF、无链路零硬件写入、
PLL回收、时序竞态、DMA生命周期和隔离调度竞态；差异checkpatch为0 errors、0 warnings、0 checks。
日志：`stability-tests-final.log`、`app-python-tests-linux.log`、`kernel-rebased-tests.log`、
`wave5-rebased-tests.log`、`kernel-release-checkpatch.log`，均在logs/kvm-stability。

早期窗口恢复f483ea42…并通过HID；发现新基线后未再安装旧目标。
后续包保留manager 9b141c5、隔离监控和M0 DTB。

## 追加复现与厂商链路判定

588f5247…（源码c0f216a18ca19）没有通过最终验收：attempt-6五轮及19模式通过，
但应用重启后立即读UDC为not attached。增加有界15秒枚举等待后，attempt-7约1秒恢复configured，
五轮及九类功能全过，最终health仍捕获两条ASoC -67，自动回退。
原始帧fixture的stop增加板端timeout 25，保留SSH 30秒上限及画面断言。

Linux 5aaac0e098ece仅将snd_soc_ret的ENOLINK改为debug，保留errno和拒绝配置语义；
这是ASoC范围的日志等级变化，不是过滤验收日志。EIO／EINVAL／ENODEV／ERANGE／EAGAIN仍报error。
actual-C覆盖100次断链、真实错误和既有返回行为；新build 9b1cb1a6…在attempt-8前四轮通过，
第五轮stream_stops 21→21、source_changes 53→57、pipelineTransitions=4，未通过。

诊断提交8386336e61a7（build 9acf4311…）限频记录readiness撤销原因。
readiness-diag-1十轮未复现；readiness-diag-2第一轮过、第二轮失败：source_changes 23→25，
管线重开一次。kernel-iso.log记录11:34:58.499 pll-unlocked，应用11:34:58.696 TRY_FMT返回ENOLINK。
这些窗口均恢复7b8372b8…、三服务active、configured、isolated=0、taint=0和实际HID，
证据在各窗口restored.json／restored-hid.log；attempt窗口为kernel-restored.json及HID日志。

厂商5.15 hdmi_rx_hw_t7.c的aml_get_tmds_valid_t7使用SQO、is_tmds_clk_stable和alignment。
hdmi_rx_hw.c中clock_lock_th=2，即线缆时钟（高倍率×4）与TMDS差不超过2MHz。
当前移植额外用模拟APLL锁定位单独撤销ready，与厂商持续链路判定不同。
修复3ff099187ea5按厂商补齐SQO及有效时钟匹配，保留5V、alignment和初始PLL锁定要求。
actual-C验证PLL位低但有效链路可查询，SQO／有效计数／alignment丢失及±2MHz边界外仍ENOLINK；
RX/VDIN全套通过，日志kernel-tmds-tests.log。该改动未消除后续真实失锁，不能作为修复完成证据。

## 最新候选结果与阻塞

Linux分支HEAD 3ff099187ea5bb1b08e0a34dc78a974f604516de，build ID
da19093a7b275128c352c0f92d735620fce168a1；One-KVM仍为672b8fd9。
attempt-9及source-diag-1/2/3累计27轮，24过、3失败；1表示该轮失败，0表示通过：

| 轮次 | 逐轮失败数 |
|---|---|
| 1–10 | 0,1,0,0,0,0,0,0,0,1 |
| 11–20 | 0,0,0,0,0,0,0,0,0,0 |
| 21–27 | 0,0,0,0,0,0,1 |

逐轮路径及计数：logs/kvm-stability/latest-candidate-rounds.json；诊断轮不能冒充正式验收。
最后一次source-diag-3第7轮，SOURCE_CHANGE 87→89、管线停止并重开一次，VDIN停止计数30→30。
RX采样每秒5次、最多4000次，仅变化时输出：12:18:16.525时5V/HPD均1，
PLL/SQO/alignment同时为0；16.726线缆时钟为0；16.926恢复720×400及28.32MHz。
Mac有效观察器在该失锁区间无显示重配，24.407的回调对应测试退出恢复EDID。
证据：source-diag-3/rx-observations.jsonl、candidate.log、focused-7.log，
以及source-display-events-3b.jsonl；此前两个空回调日志无效，不用于推断源稳定。

这是真实接收链路失锁，不是单独的FDET无效值、VDIN队列错误或应用永久停止。
尚不能区分发送端瞬断、线缆与RX PHY；Mac无重配不等于电气信号未变。
需受控HDMI源／电气观测或厂商5.15同链路对照，不能凭现有证据继续猜寄存器或掩盖失锁。
因此停止正式部署，未执行最新候选部署后的九类全量回归及四次失锁音频门禁。
最终final-restored-health.json确认7b8372b8…、三服务active、configured、isolated=0、taint=0及运行哈希；
source-diag-3/restored-hid.log确认键盘按下/释放、绝对/相对鼠标、点击和滚轮。两锁已释放。

## 窗口回退保障

针对M1事故中停止manager卡住的问题，final-board的stop统一限30秒，
超时／非零返回只报告，继续恢复文件；先sync，再有界daemon-reload。
save先将恢复程序、元数据和rollback.sh写入备份，不依赖Mac或staging。
sudo执行rollback.sh reboot恢复并重启，verify核对文件／模块／身份，另查隔离状态及实际HID。
首窗口入口：`/var/backups/vim4-kvm-stability-diag6/rollback.sh`。
故障测试覆盖两个stop及daemon-reload全部超时仍恢复和sync，以及删除payload后执行回退脚本。
