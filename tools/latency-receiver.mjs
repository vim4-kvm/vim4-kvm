// Usage: PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node ... URL SECONDS
// Read frame IDs from actual decoded pixels. Source and receiver must run on
// the same Mac; no device clock or RTP sender clock is used for latency.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.argv[2] || 'http://192.168.50.210:8080';
const seconds = Number(process.argv[3] || 20);
const verifyCoherence = process.argv.includes('--verify-coherence');
const width = Number(process.argv.find(arg => arg.startsWith('--width='))?.split('=')[1] || 3840);
if (![1280, 1920, 3840].includes(width)) throw new Error('Unsupported --width');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage();
  await page.addInitScript(() => {
    window.peers = [];
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) { super(...args); window.peers.push(this); }
    };
  });
  await page.goto(url);
  await page.waitForFunction(width => document.querySelector('video')?.videoWidth === width,
    width, { timeout: 30000 });
  await page.waitForTimeout(3000);
  const stats = () => page.evaluate(async () => {
    for (const peer of window.peers) {
      for (const stat of (await peer.getStats()).values()) {
        if (stat.type === 'inbound-rtp' && stat.kind === 'video') return stat;
      }
    }
  });
  await page.evaluate((verifyCoherence) => {
    const video = document.querySelector('video');
    const canvas = document.createElement('canvas');
    canvas.width = 32; canvas.height = verifyCoherence ? 216 : 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    window.latencyFrames = []; window.invalidMarkers = 0;
    window.incoherentMarkers = 0;
    window.keepLatency = false;
    let previous = -1, callbacks = 0;
    window.measureLatency = true;
    const frame = (now, metadata) => {
      if (!window.measureLatency) return;
      // GPU-to-CPU readback is intrusive at 4K. Sample about 10 times/second,
      // and report its cost separately rather than calling it transport delay.
      if (++callbacks % 6 !== 0) {
        video.requestVideoFrameCallback(frame);
        return;
      }
      const readStartMs = performance.timeOrigin + performance.now();
      // Coordinates are normalized to the source window's logical 1920x1080.
      ctx.drawImage(video, 20 / 1920 * video.videoWidth,
        verifyCoherence ? 0 : 85 / 1080 * video.videoHeight - 2,
        1880 / 1920 * video.videoWidth, verifyCoherence ? video.videoHeight : 4,
        0, 0, 32, canvas.height);
      const pixels = ctx.getImageData(0, 0, 32, canvas.height).data;
      const readWord = (row) => {
        let word = 0;
        for (let bit = 0; bit < 32; bit++) {
          word = ((word << 1) | (pixels[(row * 32 + bit) * 4] > 128 ? 1 : 0)) >>> 0;
        }
        return word;
      };
      const word = readWord(verifyCoherence ? 17 : 0);
      const id = (word >>> 8) & 65535;
      const checksum = ((id >>> 8) ^ (id & 255) ^ 0xa5) & 255;
      if ((word >>> 24) === 0xa5 && (word & 255) === checksum) {
        if (verifyCoherence && window.keepLatency &&
            (readWord(108) !== word || readWord(199) !== word)) {
          window.incoherentMarkers++;
        }
        if (id !== previous && window.keepLatency) {
          window.latencyFrames.push({ id, readStartMs,
            observedMs: performance.timeOrigin + performance.now(),
            presentationMs: performance.timeOrigin + metadata.presentationTime,
            expectedDisplayMs: performance.timeOrigin + metadata.expectedDisplayTime,
            decodeSeconds: metadata.processingDuration,
            clockOffsetMs: Date.now() - (performance.timeOrigin + performance.now()) });
          previous = id;
        }
      } else if (window.keepLatency) { window.invalidMarkers++; }
      video.requestVideoFrameCallback(frame);
    };
    video.requestVideoFrameCallback(frame);
  }, verifyCoherence);
  // Warm up canvas allocation and GPU readback before measuring.
  await page.waitForTimeout(3000);
  await page.evaluate(() => { window.keepLatency = true; });
  const before = await stats();
  await page.waitForTimeout(seconds * 1000);
  const after = await stats();
  const result = await page.evaluate(() => {
    window.measureLatency = false;
    return { frames: window.latencyFrames, invalidMarkers: window.invalidMarkers,
      incoherentMarkers: window.incoherentMarkers };
  });
  console.log(JSON.stringify({ before, after, verifyCoherence, ...result }, null, 2));
  if (result.frames.length < seconds * 5) {
    if (process.env.VIM4_TEST_SCREENSHOT) await page.screenshot({ path: process.env.VIM4_TEST_SCREENSHOT });
    throw new Error('Too few valid HDMI markers; inspect the emitted samples');
  }
  if (verifyCoherence && (result.incoherentMarkers || result.invalidMarkers)) {
    throw new Error('Frame coherence check failed; inspect the emitted samples');
  }
  await page.close();
} finally {
  await browser.close();
}
