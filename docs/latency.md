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
