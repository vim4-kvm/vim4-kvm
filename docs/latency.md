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
