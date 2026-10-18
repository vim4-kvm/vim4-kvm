import { loginManager } from './manager-login.mjs';
// Play a non-silent HDMI source before running. Decodes the application's Opus
// WebSocket stream; silence is a failure, not evidence of working audio.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
const origin = 'http://192.168.50.210:8080';
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: [`--unsafely-treat-insecure-origin-as-secure=${origin}`] });
try {
  const page = await browser.newPage();
  await loginManager(page.context(), origin);
  await page.goto(origin + '/api/setup');
  const result = await page.evaluate(async () => {
    let frames = 0, peak = 0, failure;
    const decoder = new AudioDecoder({
      output(audio) {
        const samples = new Float32Array(audio.numberOfFrames);
        audio.copyTo(samples, { planeIndex: 0, format: 'f32-planar' });
        for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
        frames += audio.numberOfFrames;
        audio.close();
      },
      error(error) { failure = error.message; },
    });
    decoder.configure({ codec: 'opus', sampleRate: 48000, numberOfChannels: 2 });
    const socket = new WebSocket(`ws://${location.host}/api/ws/audio`);
    socket.binaryType = 'arraybuffer';
    socket.onmessage = event => {
      if (!(event.data instanceof ArrayBuffer)) { failure = String(event.data); return; }
      const view = new DataView(event.data);
      decoder.decode(new EncodedAudioChunk({ type: 'key', timestamp: view.getUint32(1, true) * 1000,
        duration: view.getUint16(5, true) * 1000, data: new Uint8Array(event.data, 15) }));
    };
    await new Promise(resolve => setTimeout(resolve, 5000));
    socket.close();
    await decoder.flush();
    decoder.close();
    if (failure) throw new Error(failure);
    return { frames, peak };
  });
  console.log(JSON.stringify(result));
  assert(result.frames >= 48000 && result.peak > 0.001, 'No audible signal decoded');
} finally {
  await browser.close();
}
