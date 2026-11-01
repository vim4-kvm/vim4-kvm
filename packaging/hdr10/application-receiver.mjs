// Video-only P0-5 receiver; no input actions, audio analysis or source changes.
// Caller owns a board-queue ticket and sampling lease. Configure the selected
// application/codec/size before invoking this bounded receiver.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { loginManager } from '../../tools/manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const [url, app, output, hdr = 'pq', duration = '20'] = process.argv.slice(2);
assert(['nanokvm', 'jetkvm', 'pikvm'].includes(app));
assert(['pq', 'sdr'].includes(hdr));
const seconds = Number(duration);
assert(seconds >= 5 && seconds <= 300);
await fs.mkdir(output, { recursive: false });
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required', '--disable-features=WebRtcHideLocalIpsWithMdns'] });
try {
  const context = await browser.newContext();
  await loginManager(context, url);
  await context.addInitScript(app => {
    if (app === 'nanokvm') localStorage.setItem('nano-kvm-vide-mode', 'h265');
    window.hdrPeers = []; window.hdrPrefix = null; window.hdrColor = null;
    const Peer = RTCPeerConnection;
    window.RTCPeerConnection = class extends Peer {
      constructor(config, options) {
        super({ ...config, encodedInsertableStreams: true }, options);
        window.hdrPeers.push(this);
        this.addEventListener('track', async event => {
          if (event.track.kind !== 'video') return;
          const { readable, writable } = event.receiver.createEncodedStreams();
          readable.pipeThrough(new TransformStream({ transform(frame, controller) {
            if (!window.hdrPrefix && frame.type === 'key') window.hdrPrefix = Array.from(new Uint8Array(frame.data));
            controller.enqueue(frame);
          }})).pipeTo(writable).catch(() => {});
          const clone = event.track.clone();
          const reader = new MediaStreamTrackProcessor({ track: clone }).readable.getReader();
          try {
            const sample = await reader.read();
            if (sample.value) {
              window.hdrColor = sample.value.colorSpace.toJSON();
              sample.value.close();
            }
          } finally { await reader.cancel(); clone.stop(); }
        });
      }
      createDataChannel(label, options) {
        const channel = super.createDataChannel(label, options);
        if (/hid|keyboard|mouse/i.test(label)) channel.send = () => {};
        return channel;
      }
    };
    const Socket = WebSocket;
    window.WebSocket = class extends Socket {
      send(data) {
        if (typeof data !== 'string') return;
        try {
          const message = JSON.parse(data);
          const kind = message.event_type || message.type || '';
          if (/key|mouse|hid/i.test(kind)) return;
        } catch { return; }
        return super.send(data);
      }
    };
    document.addEventListener('play', event => {
      if (event.target instanceof HTMLMediaElement) event.target.muted = true;
    }, true);
  }, app);
  const page = await context.newPage();
  await page.goto(url);
  await page.waitForFunction(() => [...document.querySelectorAll('video')].some(v => v.videoWidth > 0)
    && window.hdrColor && window.hdrPrefix, null, { timeout: 45000 });
  const stats = () => page.evaluate(async () => {
    for (const peer of window.hdrPeers) {
      const reports = await peer.getStats();
      for (const report of reports.values()) {
        if (report.type === 'inbound-rtp' && report.kind === 'video' && report.framesDecoded > 0)
          return { ...report, codec: reports.get(report.codecId) };
      }
    }
    throw Error('No decoded video');
  });
  const before = await stats();
  await page.waitForTimeout(seconds * 1000);
  const after = await stats();
  const evidence = await page.evaluate(() => ({ color: window.hdrColor, prefix: window.hdrPrefix }));
  const result = { app, hdr, elapsed: (after.timestamp - before.timestamp) / 1000,
    decoded: after.framesDecoded - before.framesDecoded,
    dropped: after.framesDropped - before.framesDropped,
    width: after.frameWidth, height: after.frameHeight, color: evidence.color, codec: after.codec };
  result.fps = result.decoded / result.elapsed;
  await fs.writeFile(`${output}/first-keyframe.h265`, Buffer.from(evidence.prefix));
  await fs.writeFile(`${output}/result.json`, JSON.stringify({ result, before, after }, null, 2));
  assert.equal(result.codec.mimeType.toLowerCase(), 'video/h265');
  assert(result.decoded > 0 && result.fps >= 59 && result.dropped === 0, JSON.stringify(result));
  if (hdr === 'pq') {
    assert.equal(result.color.transfer, 'smpte2084');
    assert.equal(result.color.primaries, 'bt2020');
    assert.equal(result.color.matrix, 'bt2020-ncl');
    assert.equal(result.color.fullRange, false);
  } else assert.notEqual(result.color.transfer, 'smpte2084');
  console.log(JSON.stringify(result));
} finally { await browser.close(); }
