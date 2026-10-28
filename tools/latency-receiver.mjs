import { loginManager } from './manager-login.mjs';
// Usage: PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node ... URL SECONDS
// --expect-codec=h264|h265 rejects an unexpected negotiated codec before sampling.
// Read frame IDs from actual decoded pixels. Source and receiver must run on
// the same Mac; no device clock or RTP sender clock is used for latency.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.argv[2] || 'http://192.168.50.210:8080';
const seconds = Number(process.argv[3] || 20);
const statsInterval = Number(process.argv.find(arg => arg.startsWith('--stats-interval='))?.split('=')[1] || 0);
if (!Number.isFinite(statsInterval) || statsInterval < 0 || (statsInterval > 0 && statsInterval < 5)) {
  throw new Error('Invalid --stats-interval (0 disables periodic snapshots; otherwise >=5 seconds)');
}
const verifyCoherence = process.argv.includes('--verify-coherence');
const noPixels = process.argv.includes('--no-pixels');
const rtpTimeline = process.argv.includes('--rtp-timeline');
const expectedCodec = process.argv.find(arg => arg.startsWith('--expect-codec='))?.split('=')[1];
if (expectedCodec && !['h264', 'h265'].includes(expectedCodec)) {
  throw new Error('Invalid --expect-codec (h264 or h265)');
}
// A CPU-backed canvas can read the entire 4K video texture before cropping.
// Prefer GPU drawing of the tiny marker; keep the old hint for overhead controls.
const cpuReadback = process.argv.includes('--cpu-readback');
const pikvm = process.argv.includes('--pikvm');
const cdp = process.env.LATENCY_CDP;
const width = Number(process.argv.find(arg => arg.startsWith('--width='))?.split('=')[1] || 3840);
if (![1280, 1920, 3840].includes(width)) throw new Error('Unsupported --width');
if (!Number.isFinite(seconds) || seconds <= 0) throw new Error('Invalid duration');
const browser = cdp ? await chromium.connectOverCDP(cdp)
  : await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
    ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }), headless: true });
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
      const reports = await peer.getStats();
      for (const stat of reports.values()) {
        if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
          return { ...stat, codecMimeType: reports.get(stat.codecId)?.mimeType };
        }
      }
    }
  });
  await page.evaluate(({verifyCoherence, noPixels, cpuReadback, rtpTimeline}) => {
    const video = document.querySelector('video');
    const canvas = document.createElement('canvas');
    canvas.width = 32; canvas.height = verifyCoherence ? 216 : 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: cpuReadback });
    window.latencyFrames = []; window.invalidMarkers = 0;
    window.incoherentMarkers = 0;
    window.keepLatency = false;
    window.latencyTimeline = [];
    window.clockDiscontinuities = 0;
    let previousClockOffset;
    let previous = -1, callbacks = 0;
    window.measureLatency = true;
    const frame = (now, metadata) => {
      if (!window.measureLatency) return;
      const samplePixels = !noPixels && ++callbacks % 6 === 0;
      // timeOrigin is fixed at navigation, while the host wall clock may slew
      // during a soak. Map each sample back to the source's current Date clock.
      let clockOffsetMs, clockUncertaintyMs;
      if (samplePixels || rtpTimeline) {
        const clockBefore = performance.timeOrigin + performance.now();
        const wallClock = Date.now();
        const clockAfter = performance.timeOrigin + performance.now();
        clockOffsetMs = wallClock - (clockBefore + clockAfter) / 2;
        clockUncertaintyMs = 1 + (clockAfter - clockBefore) / 2;
        if (window.keepLatency && previousClockOffset !== undefined &&
            Math.abs(clockOffsetMs - previousClockOffset) > 2) window.clockDiscontinuities++;
        previousClockOffset = clockOffsetMs;
      }
      if (window.keepLatency) window.latencyTimeline.push({
        // Keep cadence on the monotonic browser clock. The optional wall-clock
        // fields allow every callback to join an independently decoded AU by
        // RTP timestamp, without increasing intrusive pixel readback frequency.
        presentationMs: performance.timeOrigin + metadata.presentationTime,
        callbackMs: performance.timeOrigin + now, presentedFrames: metadata.presentedFrames,
        ...(rtpTimeline ? {
          rtpTimestamp: metadata.rtpTimestamp,
          presentationWallMs: performance.timeOrigin + metadata.presentationTime + clockOffsetMs,
          receiveWallMs: Number.isFinite(metadata.receiveTime)
            ? performance.timeOrigin + metadata.receiveTime + clockOffsetMs : undefined,
          decodeSeconds: metadata.processingDuration, clockOffsetMs, clockUncertaintyMs,
        } : {})});
      // GPU-to-CPU readback is intrusive at 4K. Sample about 10 times/second,
      // and report its cost separately rather than calling it transport delay.
      if (!samplePixels) {
        video.requestVideoFrameCallback(frame);
        return;
      }
      const readStartMs = performance.timeOrigin + performance.now() + clockOffsetMs;
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
            rtpTimestamp: metadata.rtpTimestamp,
            receiveMs: Number.isFinite(metadata.receiveTime)
              ? performance.timeOrigin + metadata.receiveTime + clockOffsetMs : undefined,
            observedMs: performance.timeOrigin + performance.now() + clockOffsetMs,
            presentationMs: performance.timeOrigin + metadata.presentationTime + clockOffsetMs,
            expectedDisplayMs: performance.timeOrigin + metadata.expectedDisplayTime + clockOffsetMs,
            decodeSeconds: metadata.processingDuration,
            clockOffsetMs, clockUncertaintyMs });
          previous = id;
        }
      } else if (window.keepLatency) { window.invalidMarkers++; }
      video.requestVideoFrameCallback(frame);
    };
    video.requestVideoFrameCallback(frame);
  }, {verifyCoherence, noPixels, cpuReadback, rtpTimeline});
  // Warm up canvas allocation and GPU readback before measuring.
  await page.waitForTimeout(3000);
  const before = await stats();
  const checkCodec = snapshot => {
    if (expectedCodec && snapshot?.codecMimeType?.toLowerCase() !== `video/${expectedCodec}`) {
      throw new Error(`Expected ${expectedCodec}, received ${snapshot?.codecMimeType || 'unknown codec'}`);
    }
  };
  checkCodec(before);
  const startedMs = await page.evaluate(() => {
    window.keepLatency = true;
    return performance.timeOrigin + performance.now();
  });
  const statsHistory = [];
  let after;
  if (statsInterval > 0) {
    statsHistory.push(before);
    const deadline = performance.now() + seconds * 1000;
    while (performance.now() < deadline) {
      await page.waitForTimeout(Math.min(statsInterval * 1000, deadline - performance.now()));
      after = await stats();
      statsHistory.push(after);
      if (!after || !before || after.ssrc !== before.ssrc || after.framesDecoded < before.framesDecoded) {
        throw new Error('Video stream changed during measurement; discard this window');
      }
      const elapsed = (after.timestamp - before.timestamp) / 1000;
      const observations = await page.evaluate(() => ({ markers: window.latencyFrames.length,
        callbacks: window.latencyTimeline.length, invalidMarkers: window.invalidMarkers,
        incoherentMarkers: window.incoherentMarkers, clockDiscontinuities: window.clockDiscontinuities }));
      console.error(JSON.stringify({ elapsedSeconds: elapsed, ssrc: after.ssrc,
        decodedFPS: (after.framesDecoded - before.framesDecoded) / elapsed,
        framesDropped: after.framesDropped - before.framesDropped,
        packetsLost: after.packetsLost - before.packetsLost,
        freezeCount: after.freezeCount - before.freezeCount, ...observations }));
    }
  } else {
    await page.waitForTimeout(seconds * 1000);
    after = await stats();
  }
  checkCodec(after);
  const result = await page.evaluate(() => {
    window.measureLatency = false;
    return { endedMs: performance.timeOrigin + performance.now(),
      timeline: window.latencyTimeline, frames: window.latencyFrames, invalidMarkers: window.invalidMarkers,
      incoherentMarkers: window.incoherentMarkers, clockDiscontinuities: window.clockDiscontinuities };
  });
  const negotiation = await page.evaluate(async () => {
    const peers = window.peers.filter(p => p.connectionState === 'connected');
    return Promise.all(peers.map(async p => ({sdp: p.remoteDescription?.sdp,
      reports: [...(await p.getStats()).values()].filter(s =>
        ['codec', 'transport', 'candidate-pair', 'local-candidate', 'remote-candidate'].includes(s.type))})));
  });
  const streamerAfter = await streamerState();
  console.log(JSON.stringify({ before, after, startedMs, noPixels, rtpTimeline, statsInterval, statsHistory,
    clockMapping: 'per-sample-wall-offset',
    readbackMode: cpuReadback ? 'cpu-preferred' : 'gpu-preferred', browserVersion: browser.version(),
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
