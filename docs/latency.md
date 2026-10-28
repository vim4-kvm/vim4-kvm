# HDMI-to-browser latency measurement

> 摘要：第一节是统一验收协议（指标定义、目标、测试矩阵），优化前必读；其后三节
> 是历史实测（Chrome 基线、板端隔离与完整帧模式、分阶段计时与分包），只在复核
> 对应结论时按标题读取。光学端到端与输入到光子延迟尚未测量。

## 优化指标与验收协议

以下是后续优化的统一协议和工程目标，不是已测达标结果，也不是硬件极限承诺。
先优化 PiKVM 与共享采集/编码链路；共享改动须回归 One-KVM、NanoKVM 和
JetKVM。各系统的 H.264/H.265 分别出结果，不混合汇总。

### 主指标与目标

| 指标 | 测量定义 | 第一阶段目标（有线局域网、4K60） |
|---|---|---|
| 软件端到端延迟 | 同一主机源端开始绘制带 ID 的帧，到浏览器提交该帧给合成器；报告 P50/P95/P99/max、有效样本数 | P50 ≤ 60ms、P95 ≤ 75ms、P99 ≤ 90ms；达标后继续降低，不能牺牲下述约束 |
| 显示更新间隔 | 每次 requestVideoFrameCallback 的 presentationTime 差值；另报 presentedFrames 跳号，以识别回调漏采 | P95 ≤ 33.4ms、P99 ≤ 50ms；单独统计 >50/100/250ms 次数和最大间隔，稳态不得出现 >250ms 停顿 |
| 持续运行后的延迟增长 | 同一连接内，在相同运动负载下比较首尾有效窗口的端到端 P50/P95 | 30 分钟后两者增长均 ≤ 1 帧（16.7ms），不得靠刷新网页恢复 |
| 实际画面更新率 | 浏览器 decoded FPS 与 presentedFrames 增量分别报告；解码率不能替代呈现率 | 60Hz 输入下两者均 ≥ 59fps；另报源端实际更新率，避免把重复源帧算流畅 |
| 丢帧、卡死与完整性 | 测量窗口内 framesDropped、packetsLost、freezeCount 的增量，三带帧 ID 一致性 | 无人工丢包的受控 LAN 验收要求零丢包、零浏览器丢帧/冻结、零撕裂标记；异常轮次保留，不静默重跑到通过 |
| 画质与带宽 | 固定场景、分辨率、帧率、码率预算；报告实际 Mbps、峰值及文字/细线/运动画面检查 | 不以降分辨率、降帧率、提高 QP 或增加带宽换取“同画质低延迟”结论 |

60/75/90ms 是本项目设定的首阶段目标；需用当前版本重新建立基线。
历史 NanoKVM 约 65ms 的结果不能直接作为当前 PiKVM/One-KVM 基线。
相同码率不代表 H.264/H.265 相同画质：跨编码器比较另设同画质实验，记录
相同参考片段与解码输出；只有实际做过参考画质评估，才报告等画质码率比。

真正的 HDMI 光子到显示器光子、鼠标输入到显示器光子延迟另外列项。
现有工具没有测到这两个终点，必须标为未测；后续需要高速摄影或光学设备。
浏览器 expectedDisplayTime 是预测值，不能作为光学验收结果。

### 测试矩阵与运行条件

- 主验收：4K60、有线 LAN、单观看者、H.264/H.265 分开；静态小字、持续高速
  滚动、运动停止后的恢复分别统计。以 60Mbps 为高画质压力档、12Mbps 为带宽
  受限档；不支持某个组合的系统标记不支持，不自动替换为其他传输模式。
- 初筛每个配置预热至少 15 秒后测量 120 秒；候选与基线交替 A/B/A，至少
  三组配对。必须先启动并稳定源端运动，再开始统计，启动抖动另行记录。
- 保留候选后做至少 30 分钟的同连接耐久测试，包括反复高速运动和静止；首尾
  使用相同的 120 秒运动窗口。帧 ID 目前 16 位，60Hz 下约 18 分钟回绕：
  耐久测试拆成独立源日志与测量窗口，浏览器连接保持不变，不能直接合并 ID。
- 首次连接、新观看者加入、断线重连、关键帧恢复、切换编码另做功能回归，
  记录首帧/恢复耗时；丢包恢复实验与零丢包 LAN 验收分开，不混合统计。
- 记录源码提交、已安装包、应用/编码器 PID、实际编码格式、分辨率、输入频率、
  码率/GOP/逐行刷新设置、浏览器版本、运行模式、屏幕刷新率、音频开关、
  实际媒体网卡路径、温度及 CPU/编码器时钟。音频开启为主验收条件。
- 构建与性能采样串行，测试期间不运行其他编码器、抓栈或性能测试；配置、
  进程或媒体路径发生变化，整轮标为受干扰并保留原始数据。

### 测量有效性与接受改动的规则

端到端像素回读本身会影响 GPU。延迟测试记录回读耗时；流畅度另跑不回读
像素的配对测试。逐帧回调只说明浏览器提交节奏，不证明屏幕真正显示了每帧。
时钟偏差须 ≤ 2ms，报告标记缺失、无效和不一致数量；不删除慢样本来美化尾部。
每个 120 秒延迟窗口至少 1000 个有效标记才用于 P99 比较；数量不足仍保留
原始记录，但不宣称尾延迟达标。卡死导致无新标记时，必须同时报告无更新时长，
不能只计算卡死前的成功帧。

单项改动至少应在三组配对中方向一致，目标延迟分位数的组间中位改善达到
3ms 且超过对照轮次自身的波动；否则标为尚无明确收益。P50 改善不能抵消
P95/P99 的明确退步，播放间隔尾部、冻结、画质、音频和恢复能力也必须通过。
达不到绝对目标时可以保留有可靠收益且无回归的阶段改进，但不得称为已达标。

分段耗时（采集、编码、发送、网络、解码、实际 jitter-buffer residence）
只用于定位，不能把来自不同帧/时钟的均值或分位数相加冒充端到端结果。
队列容量、目标缓冲时间和平均 FPS 都不能单独构成优化成功证据。
目前 PiKVM 0/0 播放策略虽降低实际缓冲，但已有帧间隔尾部变差的记录；按本
协议仍需解决和复测，不能直接作为最终通过版本。

每轮保留原始日志和配置，报告基线/候选的各分位数、配对变化、流畅度、画质
检查及失败轮次。只提交验证过的改动；没有新收益时保留已验证配置，并记录
下一处可测瓶颈，不为追求数字无限缩小缓冲或使用未验证的编码器超频。

These diagnostic tools match frame IDs drawn on the Mac's AML HDMI display
with IDs read from decoded browser video. Run the source and receiver on the
same Mac. Exclusive access to the board and HDMI source is required: concurrent
encoder tests, service restarts or configuration changes invalidate the run.
Physical end-to-end and Safari validation are pending; preliminary concurrent
runs are not performance acceptance results. A controlled Chrome software-endpoint
baseline is recorded below.

Compile the source without starting a hardware test:

```sh
swiftc tools/latency-source.swift -o /tmp/vim4-latency-source
```

With NanoKVM already streaming 3840x2160 H.264, start the source in one terminal
and promptly run the receiver in another. The source window closes automatically.
Use `--motion` for scrolling content; omit it for a mostly static scene.
For the RTK UHD HDR EDID, prefix the source command with
`VIM4_HDMI_DISPLAY=RTK`; the default display-name match remains `AML`.

```sh
mkdir -p logs
/tmp/vim4-latency-source 65 --motion > logs/motion-source.jsonl
```

```sh
PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
  node tools/latency-receiver.mjs http://192.168.50.210:8080 20 \
  > logs/motion-receiver.json
python3 tools/latency-summary.py logs/motion-source.jsonl logs/motion-receiver.json
```

The receiver requires Chrome and Playwright, an accessible video page, and an
existing authenticated session if authentication is enabled. It samples every
six video callbacks after warming up pixel readback. Record service PID, video
configuration and encoder version before and after each run; reject runs with
changes. In PiKVM mode the script rejects changes to the reported streamer
parameters and codec; service PID and encoder version still require separate checks.

For PiKVM, add `--pikvm` and provide `PIKVM_USERNAME` / `PIKVM_PASSWORD`;
the receiver opens an isolated authenticated context and enables multimedia.
It does not change the board's codec or bitrate. `LATENCY_CDP` can point to a
dedicated test Chrome debugging endpoint when an externally launched browser is
needed; the context is closed afterward but the externally owned browser remains
running. Never use a personal browser profile for this test endpoint.
Optional `LATENCY_LOCAL_IP` / `LATENCY_REMOTE_IP` restrict ICE candidates for a
controlled interface test (disable Chrome's mDNS candidate obfuscation for this
case). These are diagnostic overrides, not application networking defaults.
The report includes negotiated codecs and candidate statistics; verify the actual
media path independently when comparing interfaces.

The receiver warms up video for 15 seconds and pixel readback for another three.
Start the source first and allow enough time for authentication, warmup and the
full measurement; the short examples above are diagnostic, not 120-second
acceptance runs. Use `--no-pixels` for the paired cadence test without GPU
readback. Both modes record presentation/callback timestamps and presented-frame
counters, including the silent tail after the final callback. The summary reports
missed callbacks separately from browser-reported dropped frames and distinguishes
active-span FPS from progress across the whole observation window. For a cadence
run an empty source log is sufficient; no marker matching is performed.

The marker canvas now uses `willReadFrequently=false`, preferring GPU drawing
before reading the small cropped marker. `--cpu-readback` restores the old CPU
canvas hint for overhead comparisons; the output records `readbackMode`. These
are browser hints, not a guarantee of canvas placement. Always report
`readbackCostMs` and use a separate no-pixels run for cadence: a CPU canvas may
read the full 4K video texture before cropping, perturbing decode and presentation.

For a staged capture, add `--rtp-timeline` to retain each callback's RTP timestamp,
receive/compositor wall times and clock uncertainty, without increasing pixel
readback frequency. Cadence still uses monotonic browser timestamps. Independently
decode the captured access units and associate each AU uniquely with its transmitted
RTP frame; do not infer source identity from a nominal frame period. Supply that
verified mapping to `tools/latency-rtp-summary.py SOURCE.jsonl RECEIVER.json MAP.json`.
The map schema is `{"ssrc":123,"frames":[{"rtpTimestamp":9000,"id":42,"valid":true}]}`.
The report keeps unmatched callbacks visible, rejects ambiguous mappings/clock
faults, and reports canvas readbacks that advanced beyond the callback's frame.
All-callback and sparse pixel-sample distributions are separate measurements;
neither includes frames for which the browser did not deliver a callback.

For a continuous soak, `latency-source.swift --motion --motion-cycle=480,900`
scrolls the background for eight minutes of each fifteen-minute cycle. Frame IDs
and optional audio/visual pulses continue during the stationary background.
Source records include `moving`; verify that both comparison windows contain
the same motion state. Use bounded summary windows when the 16-bit ID wraps.

`VIM4_TEST_CHROME=/absolute/path/to/browser` selects a fixed browser executable
for this receiver and `one-kvm-smoke.mjs`; otherwise both use the installed Chrome
channel. Record the actual version in every run. Automatic updates between runs
invalidate a matched browser comparison even when the driver change is unchanged.

For a long single-connection run, add `--stats-interval=60` to the receiver.
Periodic video statistics are stored in `statsHistory`; progress goes to stderr,
leaving stdout as one JSON document. With a source long enough for startup and
the full 1800-second measurement, compare the first and last two-minute windows:

```sh
python3 tools/latency-summary.py source.jsonl receiver.json --window-start=0 --window-seconds=120
python3 tools/latency-summary.py source.jsonl receiver.json --window-start=1680 --window-seconds=120
```

Boundaries must match periodic snapshots within two seconds. Source records are
selected by time before matching IDs, so a 16-bit ID wrapping during the soak
cannot accidentally match a frame from the other epoch. The full unsliced source
log still rejects duplicate IDs. Keep the source and browser on the same Mac.

`presentationMs` measures source draw start to browser compositor submission.
`readStartMs` includes JavaScript callback scheduling; `observedMs` additionally
includes pixel readback. Readback can perturb playback, so its cost is reported
separately. `expectedDisplayMs` uses a prediction, not observed screen emission.
See the [video frame callback specification](https://wicg.github.io/video-rvfc/)
for timestamp semantics. Headless Chrome measurements are software endpoint
latencies, not physical glass-to-glass latency; the latter requires an optical
measurement. Retain outliers and report static and moving scenes separately.

New receiver logs bracket `Date.now()` with monotonic samples and apply that
wall-clock offset to each pixel sample's endpoint timestamps. This accounts for
wall-clock slewing relative to the fixed navigation `timeOrigin`; it does not
subtract media or readback time. `clockMapping`, raw `clockOffsetMs` and bounded
`clockUncertaintyMs` record the method. The uncertainty includes one millisecond
for Date quantization; uncertainty above 2ms or an observed offset jump above 2ms
invalidates the run. Legacy logs without this calibration retain the original
absolute-offset limit of 2ms; they are not silently reinterpreted.
The summary also rejects unmatched/wrapped IDs and negative latencies. Raw logs
belong in the ignored `logs/` directory.

## Chrome baseline, 2026-10-13

In response to perceived Safari delay, measured Chrome separately with the tools
above. Safari WebDriver was disabled; the user chose to measure Chrome only.
These numbers do not establish Safari latency or the cause of its perceived delay.

Board package `1.0.3+vim4.20261013.3`, 3840×2160, 12000 Kbps, GOP120,
FPS limit 0, custom encoder, no experimental QP/row-refresh overrides. Service PID
3925 and settings were identical before and after both runs. Each run sampled 20s
after warmup; the source window ran for 35s and closed automatically.

| Scene | Draw start → compositor submission median / p99 / max | Decoded fps | Received Mbps |
|---|---|---|---|
| Mostly static test pattern | 80.70 / 90.66 / 140.87 ms | 59.99 | 5.12 |
| Scrolling test pattern | 81.66 / 88.84 / 88.97 ms | 60.04 | 12.23 |

Both runs reported zero dropped frames, lost packets, freezes and invalid markers.
Pixel samples numbered 173/184; sparse samples may miss short spikes. Static-run
getStats deltas gave mean decode time 4.23ms and actual jitter-buffer residence
0.87ms. Target/minimum jitter-buffer statistics are not actual residence and must
not be substituted for it. Queue capacity in code does not prove queue occupancy.

Pixel readback itself cost a median 17.60ms static / 12.30ms moving. It is excluded
from the compositor-submission interval but can still perturb playback. The result
is neither physical glass-to-glass latency nor keyboard/mouse-to-display latency.
No application code or production configuration was changed, and the service
was not restarted for this measurement.
Logs: `logs/latency-current-{static,motion}-{source.jsonl,receiver.json,summary.json}`
and `logs/latency-current-{before,after}.log` (ignored by Git).

## Board-side isolation and completed-frame mode

GStreamer's latency tracer on the live application measured these post-warmup
intervals during the moving pattern (1224 frames, approximately 20s):

| Stage | Median / p99 / max, ms |
|---|---|
| Raw-video queue | 0.116 / 0.182 / 0.584 |
| amlvenc | 11.83 / 13.37 / 14.55 |
| vfmcapsrc output → appsink input | 12.52 / 14.24 / 16.01 |

This does not measure HDMI scanout, kernel capture before vfmcapsrc, the appsink
pull wait, Go channel residence or network send time. It rules out sustained
backlog in the measured raw-video queue for this run, not every queue in the system.
Tracing used a temporary service drop-in which was removed after capture.

The driver state showed RDMA enabled and game mode 0. In this path,
`last_wr_vfe` defers delivery of a completed frame to the following interrupt.
Force mask `0x3` selects BIT0|BIT1 (completed-frame game mode 1). BIT2 is not used:
its same-buffer read/write path needs synchronization absent from this capture chain.

Matched moving-pattern measurements with three marker bands:

| Mode | Draw→compositor median / p99 / max, ms | FPS | Coherent samples |
|---|---|---|---|
| Explicitly disabled | 68.60 / 77.46 / 83.77 | 59.99 | 185/185 |
| Forced completed-frame mode (`0x3`) | 52.24 / 71.11 / 72.54 | 59.98 | 159/159 |

Both runs had zero dropped frames, lost packets, freezes and invalid markers.
The median difference is 16.35ms, approximately one 60Hz frame. These are short
sequential Chrome software-endpoint runs; browser scheduling varies between runs,
and sparse marker sampling is not proof that every possible tear is absent.
Safari, optical latency, HDR/interlaced sources and physical hotplug remain untested.

`game_mode 0` restores **automatic policy**, not a forced disable. An initial
attempt at the off control actually ran with mode `0xb` and is not valid evidence
of an off/on difference. The accepted off control first selected `3`, then `c`
(force off), and verified actual mode 0 in the driver's state dump. Always verify
the actual mode, not just the global module parameter.

`tools/hdmi-setup.sh` now selects `0x3` on start by default. A service environment
override `HDMI_LOW_LATENCY=0` restores the previous vendor automatic policy on the
next HDMI service start. It is not a guaranteed force-off switch. No kernel binary,
encoder QP/GOP or frontend implementation was changed for this optimization.

To check frame coherence, pass `--verify-coherence` to **both** latency-source
and latency-receiver. The source repeats the same frame ID near the top, middle
and bottom; the receiver reads all three from one decoded frame and reports
`incoherentMarkers`, failing the run on invalid or mismatching markers. This uses
a taller readback canvas than the single-band test, so compare only matching
test settings. The summary retains the incoherent count when this mode is enabled.
Raw evidence: `logs/latency-gst-trace*`, `logs/latency-vdin-{off,on}-*`.

### Continuous-session confirmation and deployment

Deployed development components `1.0.3+vim4.20261013.4` and restarted the HDMI
service. Actual driver mask was `0x3`. A fresh 20s receiver run measured median
65.00ms / p99 70.98ms, 60.04fps, no drops/loss and 186 coherent marker samples.
The absolute median differed from the earlier separate-session 52ms run, so a
continuous-session off/on/off control was run to remove session-start variation.

The same source, encoder process and Chrome connection remained active for 70s;
only the driver mode changed at approximately 25s and 50s after source start.
The analysis excludes 3s after and 2s before each mode transition:

| Continuous phase | Samples | Median / p99 / max, ms |
|---|---|---|
| Off | 153 | 81.91 / 89.53 / 92.60 |
| On | 190 | 65.09 / 75.56 / 76.15 |
| Off again | 219 | 81.73 / 87.38 / 92.32 |

The reversible median reduction is 16.6–16.8ms. Across the complete run,
59.98fps, no dropped frames/lost packets, and no invalid or incoherent markers
were reported. CPU governor was performance; packet sizing used the default
1200 (no LAN packet-size override present). Evidence is in
`logs/latency-continuous-*`, including locally timestamped mode transitions.

The final state was restored to forced completed-frame mode `0x3`, matching the
new startup default. Temporary tracing overrides were removed, production QP/GOP
remained unchanged, and the service/file health checks passed. The isolated package
build and verification passed, including 32 workspace Python tests, deployment
tests, both Go targets and frontend compilation. This validates service restart,
not a new power-cycle or all HDMI modes. Source/receiver coherence tool changes
were compiled/syntax checked and exercised in the hardware runs above.

## Per-stage timing and LAN packet sizing

Development components `1.0.3+vim4.20261013.5` add opt-in timing (disabled
normally). `VIM4_VIDEO_TIMING=1` records application read/send intervals;
`GST_DEBUG=vfmcapsrc:4` additionally records kernel delivery to userspace dequeue.
See NanoKVM/deploy/vim4/VIDEO.md for clock boundaries. Summarize one session:

```sh
python3 tools/video-timing-summary.py application.log capture.log
```

The tool excludes the first six seconds / 360 capture deliveries, joins read/send
records by PTS, filters to one viewer, and rejects restarted sessions or mismatched
frame sizes. Delivery sequence gaps are not a complete source-frame loss counter.

Sequential 20s moving-pattern Chrome tests used 3840×2160 at 60Hz, 12000 Kbps,
GOP 120, performance governors, completed-frame mode 0x3 and unchanged QP settings.
Only RTP packet sizing changed; both direct LAN interfaces had MTU 1500.

| Interval, ms | RTP 1200 median / p99 / max | RTP 1400 median / p99 / max |
|---|---|---|
| Kernel delivery → dequeue | 0.038 / 0.056 / 0.081 | 0.037 / 0.057 / 0.103 |
| Source PTS → encoded sample copied | 11.848 / 13.186 / 14.675 | 11.848 / 13.101 / 14.881 |
| Go handoff | 0.066 / 0.100 / 0.141 | 0.067 / 0.108 / 0.143 |
| Ordinary-frame send | 0.632 / 3.901 / 5.336 | 0.570 / 3.507 / 5.012 |
| I-frame send | 9.289 / 10.425 / 10.425 | 7.807 / 9.044 / 9.044 |
| Draw → browser compositor | 65.467 / 76.069 / 79.095 | 65.818 / 71.751 / 71.945 |

Each run contained 11 measured I frames. Their median sizes differed (271991 vs
264788 bytes); median send time normalized by size also fell, from 35.45 to
31.35 microseconds per decimal KB. This supports reduced sending overhead, not a
lower median end-to-end delay. Neither run had reported browser drops/loss,
incoherent markers or delivery sequence gaps. Observed rates were 59.99fps.
Sparse marker sampling and short runs do not guarantee losslessness for all content.

Installed the existing NanoKVM-Pro/deploy/vim4/rtp-lan.conf as
`/etc/systemd/system/nanokvm.service.d/rtp-lan.conf` on this board. This is a
LAN-specific override, not the default for unknown/VPN paths. Temporary timing
overrides were removed and NanoKVM restarted. No bitrate, QP, GOP, resolution,
frame-drop policy or frontend changes were used for this optimization.

A separate 1080p diagnostic measured 55.23ms median / 60.93ms p99 at 59.98fps,
with no reported drops/loss or incoherent markers. An earlier attempt had too few
valid markers and was rejected. Resolution was restored to 4K; separate-session
differences cannot establish how much latency resolution alone causes.

Evidence: `logs/latency-stage{1200,1400}-*`, `logs/latency-1080-debug-*`.
The isolated ARM64 build, both Go targets, frontend, package checks and deployment
health checks passed; the workspace suite passed 34 tests after adding timing-log
validation. These are software endpoint measurements, not optical or Safari results.

Final uninstrumented 20s moving-pattern validation (`logs/latency-final1400-retry-*`):
59.99fps, 12.19 Mbps received, draw→compositor median 66.79ms / p99 72.53ms /
max 72.62ms, zero browser drops/loss/freezes and 172 coherent samples. Kernel
`frames_dropped` remained zero. Clock mapping stayed within 0.9ms; pixel readback
itself cost a median 14.30ms and is reported separately. The first final attempt
(`logs/latency-final1400-*`) exceeded the 2ms clock validation limit (2.6ms), so
its latency result was rejected despite zero reported drops/loss.

The board retains 4K, 12000 Kbps and GOP 120, with no experimental QP/intra-refresh
or timing environment settings. Package integrity and service checks passed.
This establishes a measured operating point, not an absolute minimum or a guarantee
of zero drops for arbitrary content, browsers or networks.
