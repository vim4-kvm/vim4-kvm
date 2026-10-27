import { loginManager } from './manager-login.mjs';
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
  ...(process.env.VIM4_TEST_CHROME ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }), headless: true,
  args: [`--unsafely-treat-insecure-origin-as-secure=${new URL(url).origin}`],
});
try {
  const page = await browser.newPage();
  await loginManager(page.context(), url);
  const direct = { messages: 0, keyframes: 0, bytes: 0 };
  // Direct sockets live in a worker, outside the page's JavaScript globals.
  page.on('websocket', (socket) => {
    if (!socket.url().includes('/direct')) return;
    socket.on('framereceived', ({ payload }) => {
      if (!Buffer.isBuffer(payload) || payload.length < 9) return;
      direct.messages++;
      direct.bytes += payload.length;
      if (payload[0] === 1) direct.keyframes++;
    });
  });
  await page.addInitScript((mode) => {
    const storedMode = { 'h264-webrtc': 'h264', 'h265-webrtc': 'h265', 'h264-direct': 'direct', 'h265-direct': 'h265-direct' }[mode];
    localStorage.setItem('nano-kvm-vide-mode', storedMode);
    window.smokePeers = [];
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) { super(...args); window.smokePeers.push(this); }
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
    // The worker reports dimensions after rendering its first decoded frame.
    await page.waitForFunction(() => Number(document.querySelector('#screen')?.dataset.mediaWidth) > 300, {}, { timeout: 45000 });
    const start = { ...direct, at: performance.now() };
    await page.waitForTimeout(seconds * 1000);
    const end = { ...direct, at: performance.now() };
    const canvas = await page.evaluate(() => {
      const c = document.querySelector('#screen');
      return { width: Number(c.dataset.mediaWidth), height: Number(c.dataset.mediaHeight) };
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
