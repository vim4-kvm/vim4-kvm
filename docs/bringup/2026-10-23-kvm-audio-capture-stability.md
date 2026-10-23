# 2026-10-23：HDMI 音频与采集稳定性调查

基线为 M0 `47878a0c611d`／One-KVM `382efb70`。保留失锁 hw_params 拒绝语义，
应用重开资格检查已通过四次真实失锁与48k／44.1k／32k／48k音频恢复，无新增 ASoC 错误。
采集根因为无效 FDET 被误判永久错误；第二候选同时修复采集与时序查询，
build ID `79cb6dac4121782ae2d4dc01a4264a5959e6025e`，严格20轮待验收。
本记录仍在更新，未更新已部署源码锁。

## 约束与源码

与 [ENOLINK 对照](2026-10-23-hdmirx-audio-enolink.md)、
[采集停止复核](2026-10-22-wave5-first-failure-audit.md) 对照；本轮不跟踪 One-KVM 系统调用。
所有板子状态变化持 Mac `vim4-board.lock`，音视频采样同时持 `vim4-heavy.lock`；
重型构建单独持 heavy 锁。临时应用每轮恢复原二进制，再释放锁。
不操作 Wi-Fi/P2P、挂起、U-Boot 或不安全 HEVC 尺寸。

独立工作树与功能分支均为 `fix/hdmi-capture-stability`：

- One-KVM：`build/kvm-stability/One-KVM`，`dce8993d` 增加有界采集计数，
  `672b8fd9` 增加音频重开资格检查。
- Linux：VM `/home/deepdream/src/linux-7.3-kvm-stability`，`bb42b834248b7`
  增加失败分支标签、限频诊断及跨 STREAMON 保留的停止 errno／帧序号。
  独立 O= `/home/deepdream/build/kernel-kvm-stability-diag`。
  后续 `e27ed8edf7fc6` 修复活动租约下无效 FDET 快照的错误分类，并累计 invalid_frames。
  `da4ffd3f85db1` 补齐时序查询、累计 source_changes；`b0683e84d9a8b` 加强竞态注入。

未切换或修改部署分支及其他任务工作树。诊断内核仅增加观测，不能称为采集修复。

## 采集根因与修复候选

第二诊断窗口先运行原 `0,1,1,0` 序列的严格计数检查，再进入完整回归。
第一轮四段均无额外停止。第二轮稳定640×480段内停止计数4→6，断言按预期失败：

```text
[78.935039] capture check: measurement error=-34 width=640 height=480 ticks=16777215 lease=640x480/2780036 pll=1 align=1
[82.137652] capture check: measurement error=-34 width=640 height=0 ticks=16777215 lease=640x480/2779994 pll=1 align=1
07:57:29.638 raw=(59,59) encoded=59 last_frame_ms=15 signal=640x480/60
07:57:32.841 raw=(93,93) encoded=93 last_frame_ms=15 signal=640x480/60
```

这是 RX 测量无效后 VDIN 主动置 vb2 队列错误，并非原始帧仍推进而编码器独自停止。
`0xffffff` 快照连续读两次可能相同，所以原有“两个快照不同才 EAGAIN”不能覆盖。
厂商5.15 `hdmi_rx_wrapper.c` 的 ready FSM 在 timing unstable 时先 skip_frame，
累积 sig_unready_cnt 到界限后才关闭输出、进入 unready；没有把每个时序异常立即当成永久停流。

修复只把**动态模式、活动采集租约下的测量 -ERANGE**改为 EAGAIN：
VDIN 现有路径将该帧标错并继续，绝不交付无效帧；RX 现有250ms工作器将连续
EAGAIN延后四次，持续异常仍清 ready、触发停流恢复。真实失锁、有效但不同的租约时序、
不支持的色彩或隔行输入仍保留原拒绝语义。非活动租约的无效测量仍 ERANGE。
新增 actual-C 测试覆盖饱和值、零高度、无效结果不发布、后续有效帧、真实失锁与有效模式变化；
RX／VDIN 全套离线测试通过。首修复 build ID
`3cbe7d0fb6b510e2dfb0ff7d2c2d82d74e32ec07`。

日志审计发现首候选32个计数不变窗口内仍有三次 bus stop／重建：08:25:01、
08:26:06、08:27:40。时序查询还有第二次独立 FDET 测量，原修复只覆盖前后状态检查；
中间 ERANGE 可触发错误 SOURCE_CHANGE，GStreamer 重协商失败，未走 vb2 队列错误。
第二修复统一三次读取的活动租约重试分类，增加源变化计数。测试在查询中间注入一致
饱和值：旧候选失败，新候选通过，且不发布时序／帧周期；后续有效帧、真实失锁仍覆盖。

证据 `logs/kvm-stability/attempt-2/kernel-window/`，包含 focused-1/2、失败现场与自动回退。
第二窗口同样核对 M0 build ID 并通过实际原生 HID 后释放锁。

## 音频语义与应用候选

7.3 `t7_hdmirx_audio_hw_params_locked()` 在开启 PLL、FRHDMIRX 前检查实际 AIF/ACR、
原生采样率和已资格确认格式；失锁返回 ENOLINK，不稳定快照返回 EAGAIN。
`prepare()` 也拒绝失效的旧 PCM。这些检查避免按旧采样率启动。
厂商 5.15 `hdmi_rx_wrapper.c` 的 FSM_SIG_STABLE／FSM_SIG_READY 同样在信号 ready 后
配置音频并启用 PLL，失去 TMDS 时清采样率、关闭音频 PLL。
厂商 TDM hw_params 本身设置本地时钟，不等价于替输入源等待重新锁定。
不能据其未返回 ENOLINK 就移除新驱动保护。若持 audio_lock 阻塞等待，接收器资格工作
及使用该锁的重配也可能无法推进；应用应退避后重开。

One-KVM 原 recovery 在睡眠前读 ready，退避后未重查；候选在睡眠后重新检查，
capture 再要求同一格式／generation 跨过 200ms 的接收器资格窗口。
仍不能把控件查询与 hw_params 变成原子事务：竞态中的 ENOLINK/EAGAIN/ERANGE
归为 `AudioSourceChanged`，关闭 PCM，交由现有串行、可取消的 recovery 重试。
源变化不再输出 capture error；真实设备／配置错误仍保留原诊断。
不修改 ASoC 全局错误过滤；直接在明确失锁时运行 arecord 仍应失败。

首音频窗口 `audio-loss/` 四次 HPD 后 API 已 streaming=true、error=null，
但浏览器全零音频，连续性失败，**不验收**。Mac AudioQueue 跨设备移除后仍保留；
后续仅重建源端队列的对照通过，支持源端失效解释。清理时 CoreAudio 尚未枚举、
set-rate 返回7；finally 已恢复应用，随后确认源端与 RX 都为48000。

对照窗口为 `audio-loss-restarted-source-2/`：每次HPD拉低5秒，同一个浏览器连接、同一个候选 One-KVM
进程，源端每次 HPD 恢复后重建独立的 440Hz AudioQueue，再设置并实读目标采样率，
等待 RX 的 link_ready=1／audio_pcm=1／audio_rate=目标值。
四次 during_loss 均为 link_ready=0；每段20秒，沿用原探针5秒稳定期与全部连续性阈值。
track-direct 共608个、tab-direct 共607个100ms窗口，bad=0；四次 API
streaming=true、error=null，应用每次一次 recovery 尝试，内核 journal 为 `-- No entries --`。
该结论不包含保持失效源端 AudioQueue 不重建的情况，也不代表物理扬声器录音。

```sh
python3 -u build/kvm-stability/locked.py python3 -u build/kvm-stability/audio-window.py
# locked.py 仅在同时取得两把锁后运行；忙时立即释放已取得的锁。
# AUDIO_LOSS_CONTINUITY_PASS
# AUDIO_RESTORED_48000
# AUDIO_NO_RESIDUAL_ERRORS_PASS
```

中间对照 `audio-loss-restarted-source/` 因共用远程 fixture 被归档、注入前失败；
移至独立 `/var/tmp/vim4-kvm-stability` 后重跑，该次不算通过。

## 诊断窗口与严格验收

使用原部署浏览器序列 `0,1,1,0`（640×480、720×400 往返），保留帧推进、颜色、
同帧标记、快照、DMA、fps>5 全部断言。应用只增加两个原子累计计数和编码累计计数，
每五秒汇总；bus stop 附最后出帧时间、即时 signal 与管线状态，内存固定。

四轮基线＋计数应用旧断言全过，但第二轮稳定720×400仍有三次 poll stop，
raw／encoded 同停于39、79、95帧。200ms RX采样未见失锁不能排除瞬态；
第二诊断内核窗口的失败分支证据才完成归因。另有自然 ASoC -67、-11。
日志 `diagnostic-1` 至 `diagnostic-4`；第一轮组合 journal 查询无条目，已补取应用日志。

首诊断内核 `1a47df98…` 在原始模式14返回 ENOLINK，现场 link_ready=0、
VDIN stream_stops=0，尚未进入应用编码，后续类别未运行；已自动回退并通过原生 HID。
保留 `kernel-window.log`／`kernel-window/` 失败结果，不算修复通过。

最终验收在每段完成15帧资格确认后、3秒 cadence／快照检查前后，要求跨 STREAMON
保留的 stream_stops、source_changes 都不增加；用 journal cursor 检查这段内应用
started／bus stop／timeout 均为零，不依赖两端时钟一致。原画面断言全部保留。
刻意 HPD／切模式区间允许正常拆管线，不要求全程累计计数为零。

```sh
python3 -u build/kvm-stability/query-acceptance.py > logs/kvm-stability/query-acceptance.log 2>&1
# attempt-4：完整窗口，再三组 final-stress；组间释放两把锁。
```

首 e27ed8ed／672b8fd9 候选：5轮旧计数序列→九类全量回归→追加3轮，再4轮。
12轮48窗口停流计数均不增，但应用日志否决零失败结论；已中止后续组并恢复基线。
前五轮 invalid_frames 持续增长而稳定窗口 stop 计数不变，说明异常帧已被丢弃；
计数也包含原有快照变化 EAGAIN，不能把每一帧都归为新增的饱和处理。

九类全量回归全部通过：hdmi-modes（19/19，包含原失败模式14）、h264、h265、
4k60、audio（48k→44.1k→48k连续性）、hid、media、gpu、manager。
证据 `attempt-3/kernel-window/regression-results.json`；各类独立日志同目录，
原始 fixture 产物位于 `full-regression/`。
20轮指历史故障的四段浏览器序列，不是将九类全量部署测试重复20次。

## 离线验证、制品与恢复

应用 VIM4 Rust：739 passed、0 failed、2 ignored；Linux 部署助手30项通过。
Mac 助手测试因 /tmp 路径安全检查失败，改在实际 Linux 构建器通过，未修改测试。
非 VIM4 `cargo check --locked` 仍受既有 hwcodec／系统 FFmpeg 缺少
`AV_HWDEVICE_TYPE_RKMPP` 阻塞；未伪造宏绕过。
内核 audio 七档ACR/AIF、无链路零硬件写入、旧PCM与PLL回收，以及 RX／时序／
VDIN／DMA生命周期全套通过；完整 Image／dtbs／modules 构建、2334模块打包及
final-window stage 校验通过。修复应用二进制 SHA256：
`3d3cf2769577c867a3cd2788c7c98c1166ca447facbac117098f0bd64f9825f5`。
最终候选 build ID 为 `79cb6dac4121782ae2d4dc01a4264a5959e6025e`，使用 M0 DTB、4ea7484 manager。
离线日志 `stability-tests-final.log`、`app-python-tests-linux.log`、`kernel-fix-tests.log`。

每个实际安装候选的窗口释放锁前都恢复原内核、模块、应用与部署辅助文件，核对运行中二进制。
首修复窗口实际恢复输出 `attempt-3/kernel-restored.json`：

```text
buildId=f483ea42fee88be39ea67c43478638be67334d6e
one-kvm=active, vim4-manager=active, UDC=configured, taint=0
one-kvm SHA256=72db30c07aa2351a27499e06d2ac28ccde3a74e1cb18d0927766a7ba35d37b0d
manager SHA256=3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1
native-hid keyboardDown=1 keyboardUp=1 absoluteMouse=true click=true wheel=true
```

相对鼠标位置也有实测位移；完整输出为 `kernel-restored-hid.log`。
第二修复的20轮验收及最终恢复仍待完成；功能分支已推送，未合入部署分支或修改源码锁。

## 并行部署导致的基线冲突

attempt-4 在安装前 save/preflight 被 build ID 检查拦截，**79cb6dac 候选没有安装**。
另一任务已正式保留内核 `aa2f875b`（build ID
`7b8372b894c98ffae12e636a325c86f2b6c85e00`）及 manager `9b141c58`。
只读核对服务均 active、UDC configured、taint=0，运行中 One-KVM 仍为原哈希；
新 manager SHA256 为 `d7a15868e4b0b2a9fcf7342e1ffb69ed63db9b983d7b55aeedb99b0faaa59901`。
证据 `attempt-4/kernel-window.log`、`parallel-deployment-identity.json`。
本任务没有覆盖该发布，也不能声称此时仍为 f483 基线；已请求用户明确后续恢复目标。
