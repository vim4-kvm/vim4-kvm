// Run with One-KVM selected and exclusive board access. Credentials are supplied
// through ONEKVM_USERNAME / ONEKVM_PASSWORD and are never printed.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
assert(args.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
const url = args.find(arg => !arg.startsWith('--')) || 'http://192.168.50.210:8080';
const username = process.env.ONEKVM_USERNAME;
const password = process.env.ONEKVM_PASSWORD;
assert(username && password, 'Set ONEKVM_USERNAME and ONEKVM_PASSWORD');
const browser = await chromium.launch({ channel: 'chrome', headless: true,
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
  await page.goto(url);
  await page.evaluate(async ({ username, password, initialize }) => {
    const api = async (path, body) => {
      const response = await fetch('/api/' + path, body ? {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      } : {});
      if (!response.ok) throw new Error(path + ' HTTP ' + response.status);
      return response.json();
    };
    const setup = await api('setup');
    if (!setup.initialized) {
      if (!initialize) throw new Error('Complete first setup or pass --initialize');
      await api('setup/init', { username, password });
    }
    await api('auth/login', { username, password });
  }, { username, password, initialize: args.includes('--initialize') });
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
    const sample = () => page.evaluate(async () => {
      const streams = [];
      for (const peer of window.testPeers) {
        for (const s of (await peer.getStats()).values()) {
          if (s.type === 'inbound-rtp') streams.push({ kind: s.kind, time: s.timestamp,
            frames: s.framesDecoded, width: s.frameWidth, height: s.frameHeight,
            dropped: s.framesDropped, lost: s.packetsLost, bytes: s.bytesReceived,
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
    await page.waitForTimeout(10000);
    const after = await sample();
    const first = before.find(s => s.kind === 'video');
    const last = after.find(s => s.kind === 'video');
    assert(first && last && last.state === 'connected' && last.frames > first.frames, 'Video did not advance');
    const emitted = last.jitterBufferEmittedCount - first.jitterBufferEmittedCount;
    const bufferMs = field => emitted > 0 && Number.isFinite(last[field]) && Number.isFinite(first[field])
      ? (last[field] - first[field]) * 1000 / emitted : null;
    console.log(JSON.stringify({ streams: after,
      fps: (last.frames - first.frames) * 1000 / (last.time - first.time),
      videoBufferMs: bufferMs('jitterBufferDelay'),
      videoTargetBufferMs: bufferMs('jitterBufferTargetDelay'),
      videoMinimumBufferMs: bufferMs('jitterBufferMinimumDelay'),
      decodeMsPerFrame: (last.totalDecodeTime - first.totalDecodeTime) * 1000 / (last.frames - first.frames),
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
