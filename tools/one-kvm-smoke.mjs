// Run with One-KVM selected and exclusive board access. Set MANAGER_PASSWORD.
// --seconds=120 --warmup=15 measures steady-state cadence. Run a physical HDMI
// motion source separately; presentation callbacks do not prove content changes.
import assert from 'node:assert/strict';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
assert(args.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
const url = args.find(arg => !arg.startsWith('--')) || 'http://192.168.50.210:8080';
const seconds = Number(args.find(arg => arg.startsWith('--seconds='))?.split('=')[1] || 10);
const warmup = Number(args.find(arg => arg.startsWith('--warmup='))?.split('=')[1] || 0);
assert(Number.isFinite(seconds) && seconds > 0 && seconds <= 3600, 'Invalid --seconds');
assert(Number.isFinite(warmup) && warmup >= 0 && warmup <= 300, 'Invalid --warmup');
const headed = args.includes('--headed');
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }), headless: !headed,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage();
let originalMode;
try {
  await page.addInitScript(() => {
    window.testPeers = [];
    window.testAudioPeak = 0;
    window.testAudioContexts = [];
    const Original = window.RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) {
        super(...args);
        window.testPeers.push(this);
        this.addEventListener('track', event => {
          if (event.track.kind !== 'audio') return;
          const audio = document.createElement('audio');
          audio.srcObject = new MediaStream([event.track]);
          audio.volume = 0;
          document.body.append(audio);
          audio.play().catch(() => {});
          const context = new AudioContext({ sampleRate: 48000 });
          const source = context.createMediaStreamSource(new MediaStream([event.track]));
          const analyser = context.createAnalyser();
          const silentOutput = context.createGain();
          silentOutput.gain.value = 0;
          source.connect(analyser).connect(silentOutput).connect(context.destination);
          window.testAudioContexts.push(context);
          context.resume().catch(() => {});
          const samples = new Float32Array(analyser.fftSize);
          setInterval(() => {
            analyser.getFloatTimeDomainData(samples);
            for (const sample of samples) window.testAudioPeak = Math.max(window.testAudioPeak, Math.abs(sample));
          }, 50);
        });
      }
    };
  });
  await loginManager(page.context(), url, { localBackend: args.includes('--local-backend') });
  await page.goto(url);
  const requestedMode = args.find(arg => arg.startsWith('--mode='))?.split('=')[1];
  if (requestedMode) {
    originalMode = await page.evaluate(async () => (await (await fetch('/api/stream/mode')).json()).mode);
    await page.evaluate(async mode => {
      const response = await fetch('/api/stream/mode', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
      if (!response.ok) throw new Error('Mode switch HTTP ' + response.status);
    }, requestedMode);
  }
  await page.goto(url);
  if (requestedMode === 'mjpeg') {
    await page.waitForFunction(() => [...document.images].some(img => img.src.includes('/stream/mjpeg') && img.naturalWidth > 0), {}, { timeout: 30000 });
    const jpeg = await page.evaluate(async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch('/api/stream/mjpeg', { signal: controller.signal });
        if (!response.ok) throw new Error('MJPEG HTTP ' + response.status);
        const reader = response.body.getReader();
        let frames = 0, previous = 0;
        while (frames < 3) {
          const { value, done } = await reader.read();
          if (done) throw new Error('MJPEG stream ended');
          for (const byte of value) {
            if (previous === 0xff && byte === 0xd8) frames++;
            previous = byte;
          }
        }
        await reader.cancel();
        const img = [...document.images].find(img => img.src.includes('/stream/mjpeg'));
        return { frames, width: img.naturalWidth, height: img.naturalHeight };
      } finally { clearTimeout(timeout); controller.abort(); }
    });
    console.log(JSON.stringify({ mjpeg: jpeg }));
  } else {
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, { timeout: 60000 });
    await page.evaluate(() => {
      // The product can mute the WebRTC track while using its separate audio
      // WebSocket. Enable this test sink to measure the received Opus samples.
      for (const peer of window.testPeers) for (const receiver of peer.getReceivers()) {
        if (receiver.track?.kind === 'audio') receiver.track.enabled = true;
      }
    });
    await page.waitForTimeout(warmup * 1000);
    await page.evaluate(() => {
      const video = document.querySelector('video');
      const cadence = window.testCadence = {
        start: performance.now(), last: null, gaps: [], callbackMissed: 0, presented: 0,
      };
      const observe = (_now, frame) => {
        if (cadence.last) {
          cadence.gaps.push(frame.presentationTime - cadence.last.presentationTime);
          const advanced = frame.presentedFrames - cadence.last.presentedFrames;
          cadence.callbackMissed += Math.max(0, advanced - 1);
          cadence.presented += advanced;
        } else cadence.firstTime = frame.presentationTime;
        cadence.last = { presentationTime: frame.presentationTime, presentedFrames: frame.presentedFrames };
        cadence.callbackId = video.requestVideoFrameCallback(observe);
      };
      cadence.callbackId = video.requestVideoFrameCallback(observe);
    });
    const sample = () => page.evaluate(async () => {
      const streams = [];
      for (const peer of window.testPeers) {
        if (peer.connectionState !== 'connected') continue;
        const report = await peer.getStats();
        for (const s of report.values()) {
          if (s.type === 'inbound-rtp') streams.push({ id: s.id, ssrc: s.ssrc,
            codec: report.get(s.codecId)?.mimeType,
            decoder: s.decoderImplementation, powerEfficientDecoder: s.powerEfficientDecoder,
            kind: s.kind, time: s.timestamp,
            frames: s.framesDecoded, width: s.frameWidth, height: s.frameHeight,
            dropped: s.framesDropped, lost: s.packetsLost, bytes: s.bytesReceived,
            keyFrames: s.keyFramesDecoded, freezes: s.freezeCount, pli: s.pliCount,
            jitterBufferDelay: s.jitterBufferDelay,
            jitterBufferTargetDelay: s.jitterBufferTargetDelay,
            jitterBufferMinimumDelay: s.jitterBufferMinimumDelay,
            jitterBufferEmittedCount: s.jitterBufferEmittedCount,
            totalDecodeTime: s.totalDecodeTime,
            energy: s.totalAudioEnergy, state: peer.connectionState });
        }
      }
      return streams;
    });
    const before = await sample();
    await page.waitForTimeout(seconds * 1000);
    const after = await sample();
    const cadence = await page.evaluate(() => {
      const c = window.testCadence;
      document.querySelector('video').cancelVideoFrameCallback(c.callbackId);
      const gaps = c.gaps.sort((a, b) => a - b);
      const percentile = fraction => gaps.length ? gaps[Math.floor((gaps.length - 1) * fraction)] : null;
      return {
        samples: gaps.length, callbackMissed: c.callbackMissed,
        presentedFps: c.last && c.last.presentationTime > c.firstTime
          ? c.presented * 1000 / (c.last.presentationTime - c.firstTime) : null,
        p50Ms: percentile(0.5), p95Ms: percentile(0.95), p99Ms: percentile(0.99), maxMs: percentile(1),
        over50Ms: gaps.filter(gap => gap > 50).length,
        over100Ms: gaps.filter(gap => gap > 100).length,
        over250Ms: gaps.filter(gap => gap > 250).length,
        noCallbackTailMs: performance.now() - (c.last?.presentationTime ?? c.start),
      };
    });
    const first = before.find(s => s.kind === 'video');
    const last = after.find(s => s.kind === 'video');
    assert(first && last && last.state === 'connected' && last.frames > first.frames, 'Video did not advance');
    assert(first.id === last.id && first.ssrc === last.ssrc && first.codec === last.codec,
      'Video stream changed during measurement; discard this window and retry');
    const emitted = last.jitterBufferEmittedCount - first.jitterBufferEmittedCount;
    const bufferMs = field => emitted > 0 && Number.isFinite(last[field]) && Number.isFinite(first[field])
      ? (last[field] - first[field]) * 1000 / emitted : null;
    console.log(JSON.stringify({ browser: browser.version(), headed, streams: after,
      fps: (last.frames - first.frames) * 1000 / (last.time - first.time),
      videoBufferMs: bufferMs('jitterBufferDelay'),
      videoTargetBufferMs: bufferMs('jitterBufferTargetDelay'),
      videoMinimumBufferMs: bufferMs('jitterBufferMinimumDelay'),
      decodeMsPerFrame: (last.totalDecodeTime - first.totalDecodeTime) * 1000 / (last.frames - first.frames),
      videoDeltas: Object.fromEntries(['keyFrames', 'freezes', 'dropped', 'lost', 'pli']
        .map(field => [field, Number.isFinite(last[field]) && Number.isFinite(first[field])
          ? last[field] - first[field] : null])),
      presentationCadence: cadence,
    }));
    if (args.includes('--audio')) {
      const peak = await page.evaluate(() => window.testAudioPeak);
      console.log(JSON.stringify({ decodedWebRTCAudioPeak: peak }));
      assert(peak > 0.001, 'No non-silent WebRTC audio decoded; play an HDMI test signal');
    }
  }
} finally {
  try {
    if (originalMode) await page.evaluate(async mode => {
      const response = await fetch('/api/stream/mode', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
      if (!response.ok) throw new Error('Restore mode HTTP ' + response.status);
    }, originalMode);
  } finally {
    await browser.close();
  }
}
