// Requires Playwright and Chrome. Opens one viewer; coordinate encoder access.
// PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node tools/video-smoke.mjs [URL] [SECONDS] [--mode MODE]
// MODE: h264-webrtc (default), h265-webrtc, h264-direct or h265-direct.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
const modeIndex = args.indexOf('--mode');
const mode = modeIndex >= 0 ? args.splice(modeIndex, 2)[1] : 'h264-webrtc';
if (!['h264-webrtc', 'h265-webrtc', 'h264-direct', 'h265-direct'].includes(mode)) throw new Error(`unsupported mode ${mode}`);
const url = args[0] || 'http://192.168.50.210:8080';
const seconds = Number(args[1] || 15);
if (!Number.isFinite(seconds) || seconds < 1 || seconds > 300) throw new Error('SECONDS must be 1..300');
// WebCodecs (Direct modes) is only exposed to secure contexts; the board serves plain HTTP.
const browser = await chromium.launch({
  channel: 'chrome', headless: true,
  args: [`--unsafely-treat-insecure-origin-as-secure=${new URL(url).origin}`],
});
try {
  const page = await browser.newPage();
  await page.addInitScript((mode) => {
    localStorage.setItem('nano-kvm-vide-mode', mode);
    window.smokePeers = [];
    window.smokeDirect = { messages: 0, keyframes: 0, bytes: 0 };
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) { super(...args); window.smokePeers.push(this); }
    };
    const OriginalSocket = WebSocket;
    window.WebSocket = class extends OriginalSocket {
      constructor(...args) {
        super(...args);
        if (!String(args[0]).includes('/direct')) return;
        this.addEventListener('message', (event) => {
          if (!(event.data instanceof ArrayBuffer) || event.data.byteLength < 9) return;
          window.smokeDirect.messages++;
          window.smokeDirect.bytes += event.data.byteLength;
          if (new Uint8Array(event.data)[0] === 1) window.smokeDirect.keyframes++;
        });
      }
    };
  }, mode);
  await page.goto(url);
  const supported = await page.evaluate(() => ({
    webcodecs: 'VideoDecoder' in window,
    h265: !!RTCRtpReceiver.getCapabilities('video')?.codecs.some((c) => c.mimeType === 'video/H265'),
  }));
  let result;
  if (mode.endsWith('webrtc')) {
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, { timeout: 45000 });
    const sample = () => page.evaluate(async () => {
      for (const peer of window.smokePeers) {
        const stats = await peer.getStats();
        for (const stat of stats.values()) {
          if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
            return { ...stat, codec: stats.get(stat.codecId)?.mimeType, connectionState: peer.connectionState };
          }
        }
      }
      throw new Error('No inbound WebRTC video stats');
    });
    const start = await sample();
    await page.waitForTimeout(seconds * 1000);
    const end = await sample();
    const decoded = end.framesDecoded - start.framesDecoded;
    result = {
      url, mode, supported, seconds: (end.timestamp - start.timestamp) / 1000,
      codec: end.codec, connectionState: end.connectionState,
      width: end.frameWidth, height: end.frameHeight,
      framesDecoded: decoded,
      decodedFps: decoded * 1000 / (end.timestamp - start.timestamp),
      framesDropped: end.framesDropped - start.framesDropped,
      packetsLost: end.packetsLost - start.packetsLost,
      bytesReceived: end.bytesReceived - start.bytesReceived,
      keyFramesDecoded: end.keyFramesDecoded - start.keyFramesDecoded,
    };
    const want = mode.startsWith('h265') ? 'video/H265' : 'video/H264';
    if (decoded <= 0 || end.connectionState !== 'connected' || end.codec !== want) {
      throw new Error(`Video smoke test failed: ${JSON.stringify(result)}`);
    }
  } else {
    // The decoder worker resizes the canvas only when it renders a decoded frame.
    await page.waitForFunction(() => document.querySelector('canvas#screen')?.width > 300, {}, { timeout: 45000 });
    const start = await page.evaluate(() => ({ ...window.smokeDirect, at: performance.now() }));
    await page.waitForTimeout(seconds * 1000);
    const end = await page.evaluate(() => ({ ...window.smokeDirect, at: performance.now() }));
    const canvas = await page.evaluate(() => {
      const c = document.querySelector('canvas#screen');
      return { width: c.width, height: c.height };
    });
    const elapsed = (end.at - start.at) / 1000;
    result = {
      url, mode, supported, seconds: elapsed, ...canvas,
      messages: end.messages - start.messages,
      messagesPerSecond: (end.messages - start.messages) / elapsed,
      keyframes: end.keyframes - start.keyframes, firstKeyframes: start.keyframes,
      mbps: (end.bytes - start.bytes) * 8 / elapsed / 1e6,
    };
    if (result.messages <= 0 || start.keyframes <= 0) throw new Error(`Video smoke test failed: ${JSON.stringify(result)}`);
  }
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
