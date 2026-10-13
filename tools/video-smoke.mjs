// Requires Playwright and Chrome. Opens one viewer; coordinate encoder access.
// PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node tools/video-smoke.mjs [URL] [SECONDS]
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.argv[2] || 'http://192.168.50.210:8080';
const seconds = Number(process.argv[3] || 15);
if (!Number.isFinite(seconds) || seconds < 1 || seconds > 300) throw new Error('SECONDS must be 1..300');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage();
  await page.addInitScript(() => {
    window.smokePeers = [];
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) { super(...args); window.smokePeers.push(this); }
    };
  });
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, { timeout: 45000 });
  const sample = () => page.evaluate(async () => {
    for (const peer of window.smokePeers) {
      for (const stat of (await peer.getStats()).values()) {
        if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
          return { ...stat, connectionState: peer.connectionState };
        }
      }
    }
    throw new Error('No inbound WebRTC video stats; select H264 WebRTC in the UI');
  });
  const start = await sample();
  await page.waitForTimeout(seconds * 1000);
  const end = await sample();
  const decoded = end.framesDecoded - start.framesDecoded;
  const result = {
    url, seconds: (end.timestamp - start.timestamp) / 1000,
    connectionState: end.connectionState,
    width: end.frameWidth, height: end.frameHeight,
    framesDecoded: decoded,
    decodedFps: decoded * 1000 / (end.timestamp - start.timestamp),
    framesDropped: end.framesDropped - start.framesDropped,
    packetsLost: end.packetsLost - start.packetsLost,
    bytesReceived: end.bytesReceived - start.bytesReceived,
  };
  console.log(JSON.stringify(result, null, 2));
  if (decoded <= 0 || end.connectionState !== 'connected') throw new Error('Video smoke test failed');
} finally {
  await browser.close();
}
