# HDMI-to-browser latency measurement

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

```sh
mkdir -p logs
/tmp/vim4-latency-source 40 --motion > logs/motion-source.jsonl
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
changes. The script does not enforce configuration stability itself.

`presentationMs` measures source draw start to browser compositor submission.
`readStartMs` includes JavaScript callback scheduling; `observedMs` additionally
includes pixel readback. Readback can perturb playback, so its cost is reported
separately. `expectedDisplayMs` uses a prediction, not observed screen emission.
See the [video frame callback specification](https://wicg.github.io/video-rvfc/)
for timestamp semantics. Headless Chrome measurements are software endpoint
latencies, not physical glass-to-glass latency; the latter requires an optical
measurement. Retain outliers and report static and moving scenes separately.

The summary rejects unmatched IDs, ID wrap, negative latencies and excessive
browser clock mapping offsets. Raw logs belong in the ignored `logs/` directory.

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
See NanoKVM-Pro/deploy/vim4/VIDEO.md for clock boundaries. Summarize one session:

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
