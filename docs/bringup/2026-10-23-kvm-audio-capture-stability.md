# 2026-10-23：HDMI 音频与采集稳定性

状态：音频四次真实失锁恢复通过；采集根因已修复，rebase 后严格20轮待验收。
最初基线 M0 `47878a0c611d`／One-KVM `382efb70`；后续临时窗口恢复目标改为
[Wave5 隔离正式部署](2026-10-23-wave5-isolation-final.md)：内核 `aa2f875bec2fc`、
build ID `7b8372b894c98ffae12e636a325c86f2b6c85e00`、manager `9b141c5833c0`。
本记录仍在更新，未推进部署分支或源码锁。

## 源码与约束

对照 [ENOLINK 基线](2026-10-23-hdmirx-audio-enolink.md) 和
[采集停止复核](2026-10-22-wave5-first-failure-audit.md)。不使用 strace。
板子变更持 Mac board 锁；全部音视频采样同时持 heavy 锁，重型构建仅持 heavy 锁。
不操作 Wi-Fi/P2P、挂起、U-Boot 或不安全 HEVC 尺寸；显示 M1 短窗口优先。

两仓功能分支均为 `fix/hdmi-capture-stability`，已推送 fork：

| 仓库／独立工作树 | 提交与用途 |
|---|---|
| One-KVM：`build/kvm-stability/One-KVM` | `dce8993d` 有界采集计数；`672b8fd9` 音频重开资格检查 |
| Linux：VM `/home/deepdream/src/linux-7.3-kvm-stability` | `ad343d8f4860a` 限频失败诊断；`ede50b1860e70` 无效FDET重试；`35742e7e2d529` 查询修复及source_changes；`12931e4a42013` 竞态测试；`c0f216a18ca19` 参数对齐 |

Linux 已 rebase 到 `aa2f875bec2fc`，没有切换 VM 主工作树。
独立 O= `/home/deepdream/build/kernel-kvm-stability-diag`，使用正式 uhd1.config。
首轮重构建发现旧输出仅调试信息压缩配置不同，未安装，改用正式配置重建。

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

首修复内核3cbe7d0f…的12轮48段停止计数未增，九类全量回归也全过，但日志审计发现
其中三次bus stop／重建，故不算零失败验收。时序查询在前后状态检查之间还有独立FDET测量，
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
退避恢复。源变化只记debug，真实设备／配置错误保留诊断。不改ASoC全局过滤，
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

首窗口audio-loss保留失效源端AudioQueue，API恢复但浏览器全零，未验收；
仅重建源队列的对照通过。另一对照共享fixture被归档，在注入前失败，不计通过。
随后改用独立/var/tmp/vim4-kvm-stability。结论不包含失效源队列不重建或物理扬声器录音。
音频入口：`python3 -u build/kvm-stability/locked.py python3 -u build/kvm-stability/audio-window.py`。

## 严格验收方法

保留原序列的帧推进、颜色、同帧标记、快照、DMA、fps>5和cadence断言。
每段完成15帧资格确认后，3秒cadence／快照采样前后要求stream_stops与source_changes
均不增加；用journal cursor检查该段应用started／bus stop／timeout为零，不依赖两端时钟。
刻意切模式／HPD区间允许正常拆管线。20轮指历史故障的四段浏览器序列，不是九类部署测试重复20次。

```sh
python3 -u build/kvm-stability/query-acceptance.py > logs/kvm-stability/query-acceptance.log 2>&1
# attempt-5：5轮 → 九类全量回归 → 3轮；随后三个各4轮的独立窗口。
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

历史临时窗口恢复f483ea42…并核对运行哈希、服务active、UDC configured、taint=0；
实际HID键盘按下／释放、绝对／相对鼠标、点击及滚轮均通过。例：
`attempt-3/kernel-restored.json`、`kernel-restored-hid.log`。
attempt-4的save/preflight发现并行任务已部署7b8372b8…，旧79cb6dac候选没有安装。
用户随后指定新恢复目标；新bundle保留9b141c5 manager、隔离监控和M0 DTB。
新恢复检查含监控active、isolated=0、taint=0、UDC configured、实际HID及运行中二进制哈希。

## rebase 后的匹配候选

源码c0f216a18ca19，tree为0b5b812d3df0276fb89071b1968d4a21704394bf；
build ID为588f5247615044abc51e07788747e7f0920fbdb7，2334模块、带BTF。
正式配置SHA256为bca0e45df6eb43177bd82f251b4133c0468dd05195b7bae8ed8f639ba21f971c。
Image为8549a43a1eec9241c1ede9b071701dcece268c50330e4dd8341076ab07ed10e7；
modules归档为f10b4d912d72648ec8597e2f042dfe9c0ecdb1fac3139e93ec5324119684246c；
M0 DTB仍为a635f8947ee77f67a43714aaa87276aff70edc0952bf40188d46853e055ce652。
完整清单在VM的kernel-kvm-stability-release-payload，Mac包为build/kvm-stability/rebased.bundle。
构建中主动释放heavy锁让M1恢复，随后从独立O=续编；证据为kernel-release-build-resumed.log。
stage校验输出STAGED与UNCHANGED_USERSPACE_AND_RUNTIME_HELPERS_VERIFIED，
除内核和修复应用外，与Wave5隔离正式包的runtime／manager哈希相同。

M1失败窗口恢复后，本任务只读核验7b8372b8…、三个服务active、UDC configured、isolated=0、
taint=0及原应用／新manager运行哈希，证据m1-recovery-baseline.json；不将它当作本任务HID验收。
目前候选尚未安装，板锁另有用户保留；严格20轮与正式部署尚未执行。
主仓离线测试191项通过（跳过5）；同步发布后的独立文档工作树197项通过（跳过9）。
