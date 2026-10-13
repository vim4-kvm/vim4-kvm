# HDMI-to-browser latency measurement

These diagnostic tools match frame IDs drawn on the Mac's AML HDMI display
with IDs read from decoded browser video. Run the source and receiver on the
same Mac. Exclusive access to the board and HDMI source is required: concurrent
encoder tests, service restarts or configuration changes invalidate the run.
Final end-to-end validation is pending; preliminary concurrent runs are not
performance acceptance results.

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
