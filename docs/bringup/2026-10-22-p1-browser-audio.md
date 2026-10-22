# 2026-10-22：P1 浏览器音频观察器复核

本轮复现的严格音频失败来自观察器新增的 WebAudio FIFO 丢样，而同一时刻的
WebRTC 解码音轨及标签页渲染输出连续。已新增直接 AudioData 检测工具，默认绕过
该 FIFO，不修改 One-KVM、Opus 参数、前端播放设置或内核。
前轮数据见[HDMI 音频分段定位](2026-10-22-p1-hdmi-audio.md)。

## 测量方法审查与修改

旧临时脚本 `build/p1-hdmi/audio.mjs` 的三个端点中，独立 Opus 解码没有播放时钟；
音轨和标签页端点都经过 `MediaStreamAudioSourceNode → AudioWorklet`。后者增加
独立生产/消费 FIFO、重采样和 WebAudio 输出时钟，不能直接充当实际播放器验收。
旧统计确实逐样本运行，并非 AnalyserNode 定时快照；但每个窗口的墙钟是主线程
收到消息的时间，不能将消息定时抖动视为源 PCM 时间戳故障。

新增 `tools/one-kvm-audio-continuity.mjs`，已登记工具目录：

- 默认用 `MediaStreamTrackProcessor` 直接消费远端音轨和受抑制标签页回环的
  `AudioData`，避免测量引入 MediaStream→WebAudio FIFO；按实际 sampleRate
  累积 100 ms 样本窗，跨输入块保留前一采样，立即关闭 AudioData。
- 保留原严格阈值：step < 0.015、420–460 Hz、RMS 0.02–0.12、peak < 0.3。
  只测已知 440 Hz 双声道同相音的第一声道，不是任意音乐质量评分。
  原始样本时间戳、窗口帧数、时间戳间隔与消息到达时间分别保留；时间戳抖动
  不直接变成波形失败。稳态从每次切换后五秒开始，启动/切换数据仍保留。
- 每 500 ms 读取 inbound-rtp audio、media-playout、已选 candidate pair；记录
  jitterBufferDelay/EmittedCount、concealed/silentConcealedSamples、concealmentEvents、
  insertedSamplesForDeceleration、removedSamplesForAcceleration、packetsLost、jitter。
  失败窗附前后 getStats 差值；平均 jitter buffer 时间按 delay 增量 / emitted 增量计算。
- `--legacy-worklet` 仅作旧路径对照，不参与产品通过判据；`--decode-opus` 可加
  接收包的独立解码与 RTP timestamp/到达时间。默认两项均关闭，避免多余音频 sink
  和主线程 encoded transform 影响验收；不改 SDP 或接收器延迟目标。
- 固定上限限制窗口、包和失败样本保存；保留最多 24 个失败窗原始样本。直接端点
  失败、样本数量不足、观察器异常均非零退出，不以输出了报告就算通过。
- `--headed` 使用实际安装的 Chrome；保存 chrome://version 的启动命令行、版本、
  可见性/焦点、AudioContext 和设备参数。`--trace=FILE` 使用 16 MiB 环形 Chrome
  media-stream trace，仅定位窗口启用；正式矩阵不带 trace。

没有用 MediaRecorder 再编码或 AnalyserNode 快照判断连续性；现有非静音 smoke
不承担严格连续性结论，本次未修改。

## 观察器丢样的同窗证据

双锁下 headless Chrome `156.0.8078.47`，32/44.1/48k 各 45 秒，启用旧 Worklet、
独立 Opus 和 Chrome trace。前两档所有端点通过；48k 发生一次：

```text
Worklet 窗结束墙钟：1792682957512.3 ms
track-worklet: step=0.1932098, hz=450, rms=0.0712298
track-direct: step≈0.005860, hz=440
tab-direct:   step≈0.006385, hz=440
Opus:         step≈0.005851, hz=440
```

Chrome 单调时钟与墙钟通过 CDP Performance.Timestamp 双边取时对齐，取时误差范围
1 ms。trace 在 `1792682957441.724 ms`、同一 100 ms 窗内记录：

```text
MediaStreamAudioTrack::OnData frame=480
WebAudioMediaStreamAudioSink::OnData frames=480
WebAudioMediaStreamAudioSink::OnData FIFO full
随后 ProvideInput：layover_delay=61.333 ms
```

丢失的是观察器 FIFO 接收的一个 480 帧块（48k 下 10 ms）；440 Hz 相位被切断，
足以造成约 0.19 的相邻样本差。同期 getStats 的丢包、concealed/silentConcealed、
concealmentEvents、插入和删除样本增量全部 0；jitter=0.001 秒，
ΔjitterBufferDelay=720、ΔemittedCount=24000，平均 30 ms。
直接音轨/标签页/独立 Opus 均无对应跳变，不能把这一失败归因于网络、NetEQ 或发送端。

源码机制与实际 trace 相符：[Chromium WebAudioMediaStreamAudioSink](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/modules/mediastream/webaudio_media_stream_audio_sink.cc)
中 `OnData()` 在 FIFO 满时不写入当前块；`ProvideInput()` 欠载时输出零。
此处是观察器的附加桥接，不是应用中原有 `<video>` 的输出。源码链接为主线解释，
实际运行的丢块证据来自本机 Chrome trace，不声称下载源码就是该二进制的构建提交。
原始证据 `logs/p1-audio-r2/compare-trace.log`、`receiver-trace.json`。

非 headless、无 trace 的第一组 32/44.1/48k 各 45 秒也出现两次 track-worklet
失败（48k，step=0.16440/0.07556）；同窗直接音轨、直接标签页和 Opus 均通过，
上述 getStats 异常计数增量仍全为 0。不是 headless 特有现象。
该组 32k 的稳态 removedSamples 增加 218、44.1k 的 insertedSamples 增加 218，
波形却全程通过。这些是播放加/减速的样本计数，不能单凭增长认定卡顿；定义见
[WebRTC stats](https://www.w3.org/TR/webrtc-stats/#dom-rtcinboundrtpstreamstats-insertedsamplesfordeceleration)。

## 工具正负对照

本地 `--calibrate --seconds=25 --legacy-worklet` 不访问板子，使用浏览器 440 Hz
连续音；直接标签页和 Worklet 各 202 个稳态窗全部通过，退出 0。
`--calibrate --seconds=20 --inject-gap` 在第 12 秒注入 20 ms 静音，直接标签页
151 个稳态窗中准确报一个失败：step=0.067123、620 Hz，退出 1。
没有放宽阈值或跳过异常；日志为 `calibration-clean-2.log`、`calibration-gap-2.log`。

开发时 CDP 命令行查询因无 `--enable-automation` 被拒绝，三个窗口采样前退出，
未计通过；改读 chrome://version，未增加自动化标志，失败日志保留。

## 浏览器设置与上板窗口

实际 Chrome 为 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`，
版本 `156.0.8078.47`。启动命令行没有 fake media/audio device，也未保留 Playwright
的 mute-audio；auto-accept-this-tab-capture 只自动选择专用测试标签页。测试禁用
后台计时器/遮挡节流，主动 bringToFront，并逐次记录 visibility/focus，避免将后台
节流混入基线。没有麦克风输入、AGC、AEC 或 noise suppression；标签页实测
44100 Hz，直接远端音轨 48000 Hz。默认检测无需 AudioContext，因此不会再增加
44.1→48k 的观察器重采样。同步日志仍记录原始 AudioData 时间戳抖动，不伪造等间隔。

实际协商 `opus/48000/2`、`minptime=10;useinbandfec=1`，没有显式 ptime/stereo
fmtp 改动。独立解码对照的稳态 RTP timestamp 增量为 960，即每包 20 ms；
主线程收包回调间隔不冒充网卡到达间隔。产品正常播放，所有 getStats 原始值保留。

每组由 `build/p1-hdmi/locked.py` 获取 Mac 的 board/heavy 双锁；拿不到 heavy
便释放 board，组间退出释放，未与两个并行任务抢用编码器或并行编译采样。
`build/p1-audio-r2/window.py` 只管理本任务音源/采样率和健康检查，不装内核或应用。
示例（两组分别运行，组间释放锁）：

```sh
AUDIO_RATES=32000,44100,48000 AUDIO_SECONDS=45 \
  python3 -u build/p1-hdmi/locked.py python3 -u build/p1-audio-r2/window.py --headed
AUDIO_RATES=88200,96000,176400,192000 AUDIO_SECONDS=30 \
  python3 -u build/p1-hdmi/locked.py python3 -u build/p1-audio-r2/window.py --headed
```

第一次高采样率组的测量全部通过，但结束后先停音再设 nominal 48k，RX 仍显示
192k，恢复检查失败。因此改为音源仍运行时设回 48k，等待 RX 确认后才停音。
这属于测试恢复脚本问题，不把失败的恢复步骤记为通过；原始日志保留。

共享窗口间另有两项变化，前置检查均曾明确拒绝而未开始采样：

- vdec 任务临时加载外部 Wave5 后已恢复原模块，但全局 taint 的历史 bit 12
  （4096）仍保留；当前 `/sys/module/wave5/taint` 为空，没有新增 WARN 位。
  不为清除历史标志重启共享板，后续精确接受 0 或 4096，并核对当前模块无 taint。
- PD 卡片任务完成保留部署（`logs/pdcard/r2-retained.json`），manager 运行 ELF
  改为 `3fc215e3de431d1c65e08e62b3179b6329e190d803ab77e89dae3c3d90728eb1`。
  本任务保留其交付，不覆盖回旧 manager。内核、Image/DTB、One-KVM 的音视频程序
  仍与前轮基线一致；后续检查固定核对这个新 manager 哈希，而非接受任意候选。

## 非 headless 两段矩阵

四组均使用真实非 headless Chrome、无 trace。第一段低档保留旧 Worklet/Opus
作对照，第一段高档只加 Opus；第二段全部使用默认直接 AudioData，不启用额外
Worklet 或 encoded transform。每档两段并执行切换，100 ms 稳态窗口如下，均通过：

| HDMI kHz | 每段时长 s | 直接音轨 A/B | 直接标签页 A/B |
|---|---:|---:|---:|
| 32 | 45 | 404/405 | 404/404 |
| 44.1 | 45 | 404/404 | 404/404 |
| 48 | 45 | 404/404 | 404/404 |
| 88.2 | 30 | 253/253 | 253/252 |
| 96 | 30 | 253/253 | 252/253 |
| 176.4 | 30 | 253/252 | 252/253 |
| 192 | 30 | 252/253 | 252/252 |

合计音轨 4447、标签页 4443 窗。所有采样点 visible/focus=true，丢包增量 0，
media-playout synthesizedSamplesDuration/Events 增量 0；jitter 1–4 ms，
各段平均 jitter buffer 11.03–50.44 ms。启用 Opus 对照的稳态 timestamp 异常为 0。
日志 `headed-low-a-2.log`、`headed-low-b-3.log`、`headed-high-a-2.log`、
`headed-high-b-3.log`；汇总 `logs/p1-audio-r2/summary.json`。

不能宣称全程没有补样：第二段 44.1k/48k 的稳态 concealedSamples 分别增加
152/120，各一个事件，silentConcealed 增量 0，约 3.17/2.5 ms。
墙钟 1792684216047.6 / 1792684272607.2 ms 附近直接音轨最大 step 均约
0.005829、标签页约 0.006364，均 440 Hz；packetsLost/Discarded 均 0。
已检测到微小 concealment，但测试音连续，不能把它扩写为可闻卡顿或保证音乐无影响。

另一个 headless 90 秒对照使 AudioContext 与 tab 同为 44100 Hz：两路直接和
两路 Worklet 各 853 窗通过，trace 只见启动欠载，无稳态 FIFO 满。
证据 `tab-fifo-4.log`、`tab-fifo-trace.json`。

## 旧结论的更正与边界

前轮所有 Worklet 失败计数保留为观察器现象，但撤回它们作为“产品播放有爆音/卡顿”
的证据，也撤回仅凭其与 NetEQ insertedSamples 临近就推测因果的做法。
本轮证明了自然出现的一次 FIFO 满与跳变的对应，不能反推每一个历史窗口都具有同样
的 trace；早期没有保存该层事件。因此既不把旧计数删除，也不声称逐一重现了旧事件。

直接标签页仍属于软件渲染回环，不能代替物理扬声器、外部 DAC 或声学录音。
非 headless 复核可排除本轮结果只存在于 headless 的解释，但不证明任意浏览器版本、
任意后台负载或长时间运行都无故障。当前证据不支持修改 ptime/FEC/stereo 或发送节奏。

最终 `final-health-hid.log` 确认 build ID
`3ed254bfa838ab50732fdce1c5134400a1663fd5`，Image/DTB/运行 One-KVM 哈希匹配
原基线；保留上述 PD manager。两服务 active、UDC configured、原 EDID RAM、
48k/2ch LPCM，VDIN 无 fault/error；实际键盘按下/释放、两种鼠标、点击和滚轮通过。
历史 taint=4096 如实保留。本轮不改应用/内核提交，主仓工具、记录与索引未提交或推送。
主仓全量 169 tests，OK（skipped=5）；Node 语法检查通过，见 `main-tests.log`。
