# 2026-10-25：透传音频 xrun 原地恢复与连续 TX

## 现场时间线与归因

接续[厂商音频桥](2026-10-25-vendor-passthrough-audio.md)和
[独立 HDR 输出开关](2026-10-25-passthrough-hdr-switch.md)。
默认及运行内核均为 `5.15.137-vim4kvm-hdrdual6`，本轮不改内核、默认启动项、EDID、
One-KVM 代码/包/配置，不播放测试音、不请求用户听感或客户端操作。
开始即通过 `/usr/bin/lockf` 阻塞取得 board/heavy 双锁后才部署、注入故障。

2026-10-25 UTC 原始日志：

| 时间 | 事件 |
|---|---|
| 07:44:17 | 前轮网页结束后 VDIN1 关闭；这不是接收器 VDIN0/RX 关闭 |
| 07:52:00.373901 | `S/PDIF[0] Playback disable` |
| 07:52:00.413068 | 原 PCM 子进程 1577 报 `[Errno 32] HDMI PCM operation failed` |
| 07:52:00.414392 | TX `audio prepare`，FRDDR 释放、EXTN close；清理还恢复原 FRHDMIRX ASRC 策略 |
| 07:52:00.668685 | 音频协调者报告 `HDMI PCM bridge exited`，进入五秒退避 |
| 07:52:06.809883 | 重新申请 SPDIF FRDDR |
| 07:52:06.890070 | TX 再次 `audio prepare / set audio / AUDIO_UNMUTE` |
| 07:53:34–07:53:52 | 后来的 UU 会话启动/关闭，VDIN1 启停；比音频故障晚约 94 秒 |

07:52 附近没有 RX 失锁、HDMI OUT HPD 或视频 modeset，没有 One-KVM PCM/采集启停记录。
07:52:07 的 UU availability 消息只是信令状态，不能倒推成 07:52:00 音频故障的原因。
因此不能将该故障归因于稍后的 UU 协议测试。

EPIPE 是 ALSA PCM xrun；**旧 check() 把 read/write/delay 错误都记录成同一句，无法从
存量日志确定最先是采集 overrun 还是播放 underrun**。异常打印发生在 finally 清理之后，
所以 Playback disable 早于 stderr 也不能证明方向。没有历史音频稳定状态的连续采样，
不能排除未被日志记录的短时源音频停顿或调度/独立时钟偏差。
已确认的放大根因是：任何 EPIPE 都退出整个桥，释放 SPDIF/TX、恢复路由，再退避重建；
这导致约六秒音频中断和重新下发 TX 参数。显示器因此重新同步是与用户现象一致的推断，
不是本轮光学测量结论。

## 修复

只修改 manager 的 `deploy/vim4_passthrough_audio.py`：

- EXTN 采集改为 nonblocking；EAGAIN/EINTR 不退出，EPIPE/ESTRPIPE 对原采集句柄
  `snd_pcm_recover`，不关闭端点、不改 mixer、不碰 SPDIF/TX prepare。
- SPDIF 使用 ALSA `stop_threshold=boundary`、`silence_threshold=0`、
  `silence_size=boundary`。核对厂商内核 `sound/core/pcm_lib.c`：该模式在 IRQ 中
  将已消费区域立即填零，供帧暂停时 DMA/TX 继续且不会循环重播旧音频。
- 用户态恢复后用 `snd_pcm_avail_update`/`snd_pcm_forward` 跳过已由静音消费的位置，
  重新补 1280 帧零队列；不调用 playback recover/prepare，不需要驱动补丁。
  不能直接对 SPDIF 调 recover：厂商 `aml_dai_spdif_prepare` 会再次通知 hdmitx。
- 音频协调者将源准备状态写入私有 `audio-source.json`；短时无音频、unstable、
  未知速率或不支持格式时，已运行的子进程静音且继续心跳，不再 teardown。
  恢复可播放源后渐入；真正的采样率变化重复确认后才重开。
- 显式关闭声音/透传、无音频能力的显示器仍停止并释放本地 PCM；无法恢复的真实端点
  丢失/永久错误仍按原退避流程处理，不伪造成功。
- `audio-pcm.json` 增加 `captureXruns`、`playbackGapFrames`、`playbackState` 和
  `inputReady`；runtime read/write 异常加操作名称，避免今后再丢失故障方向。
  仅打开原 DEV=6/DEV=1，绝不打开 One-KVM 的 DEV=0 或改变其 ASRC 所有权。

## 自动故障注入

不操作用户 Mac/UU、不切 EDID。先短测，再在十分钟窗口开始时重复：
仅对桥子进程 `SIGSTOP` 250ms、750ms，超过 2048 帧环约 42.7ms 的缓冲，
finally 中 SIGCONT。真实 EXTN 溢出并读到 EPIPE，不是用假日志替代恢复路径。
播放端由内核继续填零，因此暂停用户进程也不会停止 TX DMA。

短测同一子进程 PID 28990，captureXruns 0→1→2，playbackGapFrames 0→11136→46464；
恢复后 ALSA playbackState 始终 RUNNING(3)，采集/播放继续推进。
注入窗口 TX `audio prepare/set audio/AUDIO_UNMUTE`、FRDDR 释放/重申请、
`S/PDIF Playback disable`、视频 modeset、RX 失锁和 HPD 日志计数全部为 0。
TX attr/AVI/DRM/Audio InfoFrame/ACR、EDID hash、HPD=1、ready=1 保持不变，OSD blank=1。

首个严格要求每次缓存 state=running 的观察器在约一分钟遇到一次 starting 而退出，
失败窗口保留，不计作十分钟通过。该次没有音频进程退出或 TX/RX 变化记录；观察器
随后改为完整保存样本，并以真实扫描帧推进（两秒停顿上限）、ready、包和链路计数验收，
同时记录 starting 次数，而不是把瞬时缓存状态等同于黑屏。

最终窗口 08:10:16 起，注入后再观察完整 **600 秒**，记录 599 个周期样本加初始基线。
同一 PCM PID 28990，captureXruns 4→5→6（两次注入），之后不再增加；播放保持 RUNNING(3)。
TX audio prepare/set audio/AUDIO_UNMUTE、FRDDR 释放/重申请、Playback disable、
视频 modeset、RX 失锁、HPD 日志计数均为 0；按驱动实际 plugin/plugout/hpd 日志再次检索亦为 0。
所有周期样本视频 running、ready=1、HPD=1、EDID hash/attr/完整包读回不变，
OSD 持续 blank=1；扫描计数速率 **59.997fps**，未出现两秒扫描停顿。

同轮保持网页 H.265 3840×2160 连接及物理动态图案 600 秒：解码 **59.9991fps**，
dropped/lost/freezes/PLI 均为 0；呈现间隔最大 38.4ms，无大于 50ms 的间隔。
122 个约五秒编码进度窗口 59.942–60.013fps、整体 59.998fps。
One-KVM PID 1756 从任务开始至结束不变；网页退出后 08:13:49 视频管线自然 auto-stop，
本地音频仍为同一 PCM PID，未引起 TX 重新同步。没有停启 One-KVM 来制造通过。

还测到独立采播时钟偏差的实际迹象：在未继续注入的十分钟段，采集与播放总排队帧数
线性趋势约 **-0.837 帧/秒（相对 48kHz 约 -17.4ppm）**，首/尾 30 样本平均
883.2→401.1 帧。原阻塞 read→write、普通 stop threshold 的有限缓冲在这种偏差下
会逐步耗尽；这提供同类周期 xrun 的机制证据，但不能追认旧日志未记录的出错方向。
新模式在耗尽后继续静音/forward，不依赖无限扩充队列，不重新准备 TX。
本轮验证的是连续链路与异常隔离，不宣称零音频缺口或完成光学/听感验收。

manager `f1a6920` 实现已合入并推送 main `fa08841`；板上 Python 模块与该 main
SHA256 相同：`f2f100ab787f5d08908e475fdb2ff776763566cbfc861d91354640865b9f8a68`。
仅替换该模块、重启音频单元，未重启视频透传、manager 或 One-KVM；Go/前端无改动，
manager 可执行文件保持上轮 `1c6b26b`。不新增备份/回退项。最终四个服务 active，
enabled/audio/hdr 偏好均 true，默认 hdrdual6 不变；自建观察/动态图案结束，双锁释放。

## 离线检查与证据

Python 单测覆盖：采集 EPIPE/ESTRPIPE 与 delay xrun 原句柄恢复、EAGAIN、真实 ENODEV
仍报错、播放落后后的 forward/静音、无 playback prepare/close、ALSA 静音保护配置、
源丢失/格式不支持/单次采样率抖动保持原子进程、确认速率变化才重开、显式关闭释放。
manager Python 共运行 212 项（12 项按环境跳过），其余通过；Go 全套测试和 vet 通过。
主仓全套 254 项（7 项按环境跳过），其余通过。

原始证据在忽略目录 `logs/passthrough-hdr/audio-recovery-*`，包括 incident/timeline、
离线测试、故障注入脚本/JSONL、内核日志与同窗口网页视频统计。
板端原始记录为 `/var/lib/vim4-kvm/audio-recovery-{probe,stability,final}.jsonl`。
只读具名 RX/TX/ALSA 状态，不读通用 audiobus regmap，不请求听感验收。
