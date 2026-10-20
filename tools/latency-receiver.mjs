import { loginManager } from './manager-login.mjs';
// Usage: PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node ... URL SECONDS
// Read frame IDs from actual decoded pixels. Source and receiver must run on
// the same Mac; no device clock or RTP sender clock is used for latency.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.argv[2] || 'http://192.168.50.210:8080';
const seconds = Number(process.argv[3] || 20);
const verifyCoherence = process.argv.includes('--verify-coherence');
const noPixels = process.argv.includes('--no-pixels');
const pikvm = process.argv.includes('--pikvm');
const cdp = process.env.LATENCY_CDP;
const width = Number(process.argv.find(arg => arg.startsWith('--width='))?.split('=')[1] || 3840);
if (![1280, 1920, 3840].includes(width)) throw new Error('Unsupported --width');
if (!Number.isFinite(seconds) || seconds <= 0) throw new Error('Invalid duration');
const browser = cdp ? await chromium.connectOverCDP(cdp)
  : await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext();
try {
  await loginManager(context, url, { localBackend: process.argv.includes('--local-backend') });
  const page = await context.newPage();
  await page.addInitScript(({localIP, remoteIP, pikvm}) => {
    window.peers = [];
    const Original = RTCPeerConnection;
    const filter = (sdp, ip) => !ip ? sdp : sdp.split('\r\n')
      .filter(line => !line.startsWith('a=candidate:') || line.split(' ')[4] === ip).join('\r\n');
    window.RTCPeerConnection = class extends Original {
      constructor(...args) {
        super(...args); window.peers.push(this);
        if (localIP) this.addEventListener('icecandidate', event => {
          if (event.candidate && event.candidate.address !== localIP) event.stopImmediatePropagation();
        });
      }
      get localDescription() {
        const d = super.localDescription;
        return d && localIP ? new RTCSessionDescription({type: d.type, sdp: filter(d.sdp, localIP)}) : d;
      }
      setRemoteDescription(d) {
        return super.setRemoteDescription(d?.sdp && remoteIP ? {type: d.type, sdp: filter(d.sdp, remoteIP)} : d);
      }
      addIceCandidate(c) {
        if (remoteIP && c?.candidate && c.candidate.split(' ')[4] !== remoteIP) return Promise.resolve();
        return super.addIceCandidate(c);
      }
    };
    if (pikvm) {
      localStorage.setItem('stream.mode', 'janus');
      localStorage.setItem('stream.multimedia', '1');
      localStorage.setItem('stream.audio', '100');
    }
  }, {localIP: process.env.LATENCY_LOCAL_IP, remoteIP: process.env.LATENCY_REMOTE_IP, pikvm});
  if (pikvm) {
    const origin = new URL(url).origin;
    await page.goto(origin + '/kvm/');
  } else await page.goto(url);
  await page.waitForFunction(width => document.querySelector('video')?.videoWidth === width,
    width, { timeout: 30000 });
  if (pikvm) {
    await page.evaluate(() => {
      const toggle = document.querySelector('#stream-multimedia-switch');
      if (!toggle.checked) toggle.click();
      document.querySelector('video').muted = true;
    });
    await page.waitForFunction(() => document.querySelector('video')?.srcObject?.getAudioTracks().length > 0,
      null, {timeout: 30000});
  }
  // The source must already be running; exclude connection and source startup.
  await page.waitForTimeout(15000);
  const streamerState = () => !pikvm ? null : page.evaluate(async () => {
    const response = await fetch('/api/streamer');
    if (!response.ok) throw new Error('Cannot read PiKVM stream configuration');
    const {result} = await response.json();
    return {params: result.params, codec: result.features.video_codec};
  });
  const streamerBefore = await streamerState();
  const stats = () => page.evaluate(async () => {
    for (const peer of window.peers) {
      if (peer.connectionState !== 'connected') continue;
      for (const stat of (await peer.getStats()).values()) {
        if (stat.type === 'inbound-rtp' && stat.kind === 'video') return stat;
      }
    }
  });
  await page.evaluate(({verifyCoherence, noPixels}) => {
    const video = document.querySelector('video');
    const canvas = document.createElement('canvas');
    canvas.width = 32; canvas.height = verifyCoherence ? 216 : 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    window.latencyFrames = []; window.invalidMarkers = 0;
    window.incoherentMarkers = 0;
    window.keepLatency = false;
    window.latencyTimeline = [];
    let previous = -1, callbacks = 0;
    window.measureLatency = true;
    const frame = (now, metadata) => {
      if (!window.measureLatency) return;
      if (window.keepLatency) window.latencyTimeline.push({
        presentationMs: performance.timeOrigin + metadata.presentationTime,
        callbackMs: performance.timeOrigin + now, presentedFrames: metadata.presentedFrames});
      // GPU-to-CPU readback is intrusive at 4K. Sample about 10 times/second,
      // and report its cost separately rather than calling it transport delay.
      if (noPixels || ++callbacks % 6 !== 0) {
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
  }, {verifyCoherence, noPixels});
  // Warm up canvas allocation and GPU readback before measuring.
  await page.waitForTimeout(3000);
  const before = await stats();
  const startedMs = await page.evaluate(() => {
    window.keepLatency = true;
    return performance.timeOrigin + performance.now();
  });
  await page.waitForTimeout(seconds * 1000);
  const after = await stats();
  const result = await page.evaluate(() => {
    window.measureLatency = false;
    return { endedMs: performance.timeOrigin + performance.now(),
      timeline: window.latencyTimeline, frames: window.latencyFrames, invalidMarkers: window.invalidMarkers,
      incoherentMarkers: window.incoherentMarkers };
  });
  const negotiation = await page.evaluate(async () => {
    const peers = window.peers.filter(p => p.connectionState === 'connected');
    return Promise.all(peers.map(async p => ({sdp: p.remoteDescription?.sdp,
      reports: [...(await p.getStats()).values()].filter(s =>
        ['codec', 'transport', 'candidate-pair', 'local-candidate', 'remote-candidate'].includes(s.type))})));
  });
  const streamerAfter = await streamerState();
  console.log(JSON.stringify({ before, after, startedMs, noPixels, browserVersion: browser.version(),
    streamerBefore, streamerAfter, negotiation, verifyCoherence, ...result }, null, 2));
  if (JSON.stringify(streamerBefore) !== JSON.stringify(streamerAfter)) {
    throw new Error('PiKVM stream configuration changed during measurement');
  }
  if (!noPixels && result.frames.length < seconds * 5) {
    if (process.env.VIM4_TEST_SCREENSHOT) await page.screenshot({ path: process.env.VIM4_TEST_SCREENSHOT });
    throw new Error('Too few valid HDMI markers; inspect the emitted samples');
  }
  if (verifyCoherence && (result.incoherentMarkers || result.invalidMarkers)) {
    throw new Error('Frame coherence check failed; inspect the emitted samples');
  }
  await page.close();
} finally {
  await context.close();
  await browser.close();
}
