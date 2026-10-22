# 2026-10-22：P1 HDMI 音频分段定位

后续[浏览器观察器复核](2026-10-22-p1-browser-audio.md)已抓到观察器 WebAudio FIFO
满后丢样；下述 Worklet 失败计数不再作为产品播放故障证据。原始记录与未覆盖边界保留。

七档 LPCM 各两段稳态和切换中，应用原生 PCM、编码前 PCM、接收到的 Opus
独立解码均连续；严格浏览器探针仍有失败。已把本次异常缩小到浏览器接收后的
播放/观察路径，不能宣称完整网页无爆音，也不能据此修改 DMA 或重采样实现。
视频、CMA 与颜色覆盖见[同轮记录](2026-10-22-p1-hdmi-video.md)。

## 分支与测量边界

基线为[正式版保留记录](2026-10-22-edge-7-3-final-retained.md)：Linux
`e0346697f2503`，build ID `3ed254bfa838ab50732fdce1c5134400a1663fd5`；
One-KVM `382efb70`、manager `7a69ced`。没有安装新内核或修改已部署源码锁。
VM 新工作树 `~/src/linux-7.3-p1-hdmi`、分支 `vim4-p1-hdmi` 保持基线，无新提交。

One-KVM 独立工作树 `build/p1-hdmi/One-KVM`，分支 `vim4-p1-audio`：
`cb5e5fc58154751c6a9b07647510301af8ef8565`，增加默认关闭的
`ONEKVM_AUDIO_STATS=1`。固定大小计数每五秒汇总原生 S16 双声道、Opus 编码前
PCM 的帧数、最大相邻差、超过 500 的差值数量、最大读取间隔、XRUN/EAGAIN；
每条 RTP 音轨统计序列缺口、编码至发送等待和写入耗时。不保存音频载荷、不用 strace。
普通音乐的相邻差可以超过 500，这只是已知 440 Hz、0.1 幅度测试音的诊断量。

ARM64 独立容器 `vim4-p1-audio-build`、独立 target volume 完成：
`cargo test --locked --features vim4 --lib` 738 passed / 2 ignored；
release 构建通过，19 条既有警告；部署助手 30 tests / OK。
诊断 ELF SHA256 `f80a1cc22e37db02e5b6bc75dfc18b5a97f8a5e04eef442bdaf662ea88daa25b`。
仅临时替换应用，窗口 finally 恢复原 ELF 并删除 `/run` 中本任务的统计环境覆盖。
没有推送；主仓仅文档改动，不提交。

## 同轮端点与严格检查

Mac 只向 HDMI 音频设备播放连续音；显式设置 nominal rate，不改默认输出。
One-KVM 正常视频/WebRTC 同时运行。程序内计数与板上 0.5 秒一次的 RX/ALSA 状态
对应以下三个浏览器端点，均只保存有限数量的 100 ms 统计：

- 接收端 encoded transform 中的 Opus，由 WebCodecs 按包顺序独立解码，排除播放时钟。
- WebRTC 接收音轨接入 AudioWorklet，包含浏览器播放时钟与音轨适配。
- 产品视频元素实际声音的专用标签页回环；要求 suppressLocalAudioPlayback，禁止房间播放。

独立解码器不会证明播放端没有问题；AudioWorklet 也不能代替物理声学验收。
接收包稳态 RTP timestamp 每包增加 960；切换停采期间允许媒体时间跳过，不当成稳态丢包。
严格阈值保持 `step < 0.015`、420–460 Hz、RMS 0.02–0.12、peak < 0.3。
切换后前五秒单列，程序内五秒汇总只有完整落入稳态的窗口才用于连续性结论。

```sh
P1_CANDIDATE=1 AUDIO_RATES=32000,44100,48000,32000,44100,48000 AUDIO_SECONDS=45 \
  /usr/bin/lockf /tmp/vim4-board.lock /usr/bin/lockf /tmp/vim4-heavy.lock \
  python3 -u build/p1-hdmi/audio-window.py
P1_CANDIDATE=1 AUDIO_RATES=88200,96000,176400,192000,88200,96000,176400,192000 \
  AUDIO_SECONDS=25 /usr/bin/lockf /tmp/vim4-board.lock \
  /usr/bin/lockf /tmp/vim4-heavy.lock python3 -u build/p1-hdmi/audio-window.py
```

| 输入 kHz | 两段稳态 100 ms 窗，Opus 独立解码 | 标签页失败窗 | 音轨探针失败窗 |
|---|---|---|---|
| 32 | 402 / 402，均通过 | 1 / 0 | 0 / 1 |
| 44.1 | 403 / 402，均通过 | 0 / 0 | 0 / 1 |
| 48 | 402 / 401，均通过 | 0 / 0 | 0 / 0 |
| 88.2 | 201 / 202，均通过 | 0 / 0 | 0 / 0 |
| 96 | 201 / 201，均通过 | 0 / 0 | 0 / 2 |
| 176.4 | 201 / 202，均通过 | 0 / 0 | 0 / 2 |
| 192 | 201 / 201，均通过 | 0 / 0 | 0 / 1 |

原生及编码前完整稳态汇总均 `steps_over_500=0, xruns=0`；原生最大差随速率变化，
32k 为 283、44.1k 为 206、48k 为 189。各档编码前最大差不超过 190。
接收端 Opus 独立解码最大差 0.00581–0.00588，稳态 RTP 时间戳异常计数均 0，
发送端 `dropped=0, errors=0`。切换和音源启停确有 PCM 跳变，不能把全程最大值
混入稳态，也不能把这些正常停采窗口从原始证据删除。

32k 标签页失败发生在墙钟 `1792679088020 ms`：690 Hz、step 0.009294、
RMS 0.06705；同一时刻独立解码与音轨探针通过，NetEQ conceal/insert/remove
计数没有同步增加。第二段 32k 音轨在 `1792679225742 ms` 出现 step 0.18256，
独立解码和标签页通过，NetEQ 计数仍未变；44.1k 音轨的 step 0.19141 附近
insertedSamples 从 2558 增到 2994。不能把所有异常统一解释成 NetEQ。

原始证据：`logs/p1-hdmi/audio-repeat-ready.log`、`audio-high-rates.log`，以及
`audio-journal-1792679046.log`、`audio-journal-1792679583.log` 和对应 status JSONL。
首个 32/44.1/48k 各 30 秒诊断轮三个端点全部通过，保留 `audio-second.log`，
不拿短轮通过覆盖后续失败。

追加两种对照，均运行原部署应用、Chrome `156.0.8078.47`：

- 产品音量设为 0，每秒确认静音/音量状态，标签页只输出本地 WebAudio 440 Hz
  连续音，远端视频继续运行。75 秒轮三个探针各 704 个稳态窗口全部通过；
  `audio-local-muted.log`。短轮未复现不能排除浏览器/探针偶发问题。
- 标签页捕获实际是 44100 Hz；将 AudioWorklet 的 AudioContext 同步改成 44100，
  排除这一级 44.1→48k 转换。32/44.1/48k 各两段 45 秒，独立 Opus 解码每段
  402–403 个稳态窗全部通过；标签页失败数依次 0/0/0/1/0/2，音轨为
  0/1/0/0/0/1。第二段 32k 标签页 step 0.11035；第二段 48k 两次为
  0.19172/0.14893，音轨另有 0.09621。证据 `audio-matched-clock.log`。
  因而不能把 AudioContext 与标签页捕获采样率不同认定为唯一原因或修复办法。

诊断 ELF 与原 ELF 均观察到接收后异常；本次提交只增加诊断能力，没有声称修复
音频播放。标签页和音轨异常经常不同步，当前还不能区分实际扬声器播放、Chrome
媒体时钟和回环/Worklet 观测自身；需要可独立录制物理输出的设备或浏览器音频内部
跟踪才能继续收敛。没有对 One-KVM 使用 strace。

## 多声道实际拒绝

持双锁运行 `python3 -u build/p1-hdmi/multi-window.py`，仅改 EDID RAM：
LPCM SAD 改为 `0f 7f 07`、公布八声道与 speaker allocation，CoreAudio 从公开的
physical formats 中选择 48k/8ch/24-bit，再发送八声道测试音。实际源端与板端输出：

```text
physical stream=90 rate=48000 channels=8 bits=24 flags=4
audio_aif: 84010a5707000013000000000000
audio_rate: 48000
audio_channels: 8
audio_pcm: 0
HDMI RX Audio State: 2
hw_params: closed
```

六次间隔三秒的采样均保持拒绝状态，未默默只取前两声道；证据
`logs/p1-hdmi/multichannel.log`。厂商 `common_drivers/sound/soc/amlogic/auge/frhdmirx_hw.c`
的 `frhdmirx_ctrl()` 对 T7 排除 PAO 多 lane 路径，当前 7.3 明确约束双声道
S16_LE，并拒绝非零 channel allocation。该测试证明 8ch 输入的检测与拒绝，
不表示实现了多声道，也未验证压缩/HBR 输入。结束恢复原 EDID 和 48k nominal rate。

## 切换错误与验证限制

非阻塞 `snd_pcm_readi` 的 EAGAIN 是等待新数据；本轮稳定采集每五秒约数百次，
不等于 XRUN。历史 ASoC `-EAGAIN` 来自 `t7_hdmirx_read_audio()` 在 hw_params
阶段拒绝不一致/校验失败的 AIF 或 ACR 快照，经 ASoC 两层打印。它与上述读取
等待是不同路径。本轮没有复现该内核警告，也没有修改错误码或证明切换竞态被消除。

测试工具首轮因 Mac 大小写不敏感目录名与 ELF 名冲突而上传失败，未安装候选；
恢复脚本又因删除不存在的覆盖文件中断，随后持锁启动原应用。工具改用 `.bin`，
仅在确实开始替换后恢复，删除覆盖文件幂等。另一次浏览器在应用 HTTP 就绪前打开
导致 45 秒无视频超时；增加就绪等待后完成上述矩阵。这两轮不计通过。
最初本地连续音对照可能混入被产品恢复的远端声音，`audio-local-control.log` 不作归因证据。

完整网页无跳变、浏览器播放时钟内部的确切故障点和物理输出验证仍未完成。
现有证据不支持凭空修改内核 DMA、GStreamer 重采样或 WebRTC 发送节奏。
