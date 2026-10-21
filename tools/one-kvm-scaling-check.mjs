// Exclusive edge check. Run latency-source.swift --motion --verify-coherence
// --no-labels on the physical HDMI desktop first. Restores mode/output/quality.
// --pause-idle-uu temporarily disables UU only when it has no connections.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
assert(args.includes('--exclusive'), 'Requires exclusive board access');
const url = args.find(x => !x.startsWith('--')) || 'http://192.168.50.210:8080';
const browser = await chromium.launch({
  ...(process.env.VIM4_TEST_CHROME ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }),
  headless: true, args: ['--autoplay-policy=no-user-gesture-required'],
});
const page = await browser.newPage();
const request = page.context().request;
let saved;
let requestedMode;
let uuPaused = false;
async function api(path, method = 'get', data) {
  const response = await request[method](url + path, data === undefined ? {} : { data });
  assert(response.ok(), `${path}: HTTP ${response.status()} ${await response.text()}`);
  return response.json();
}
function verifyMarkers(markers) {
  assert(markers.every(m => m.valid && m.id === markers[0].id), `Bad scene markers: ${JSON.stringify(markers)}`);
}
async function inputState() {
  const input = await api('/api/video/input-status?device=/dev/video_cap');
  assert.equal(input.state, 'locked');
  assert.deepEqual([input.width, input.height], [3840, 2160], 'Output scaling changed HDMI timing');
  if (args.includes('--require-hdr')) {
    const status = execFileSync('ssh', ['vim4', 'sudo', '-n', 'cat',
      '/sys/kernel/debug/fe398000.hdmi-receiver/status'], { encoding: 'utf8', timeout: 5000 });
    assert.match(status, /^hdr_input: 1$/m, 'HDMI is not carrying HDR');
    assert.match(status, /^hdr_capture: 1$/m, 'HDR mapping is not enabled');
    return { ...input, hdrInput: true };
  }
  return input;
}
await page.addInitScript(() => {
  window.scalingPeers = [];
  const Peer = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends Peer {
    constructor(...a) { super(...a); window.scalingPeers.push(this); }
  };
  window.scalingMarkers = bitmap => {
    const canvas = document.createElement('canvas'); canvas.width = 32; canvas.height = 3;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    for (let row = 0; row < 3; row++) for (let bit = 0; bit < 32; bit++)
      ctx.drawImage(bitmap, bitmap.width * (20 + (bit + .5) * 1880 / 32) / 1920,
        bitmap.height * [85, 540, 995][row] / 1080, 1, 1, bit, row, 1, 1);
    const pixels = ctx.getImageData(0, 0, 32, 3).data;
    return [0, 1, 2].map(row => {
      let word = 0;
      for (let bit = 0; bit < 32; bit++) word = (word * 2 + (pixels[(row * 32 + bit) * 4] > 128 ? 1 : 0)) >>> 0;
      const id = (word >>> 8) & 65535;
      return { id, valid: (word >>> 24) === 0xa5 && (word & 255) === (((id >>> 8) ^ (id & 255) ^ 0xa5) & 255) };
    });
  };
});

async function configure(mode, video) {
  const newMode = mode !== requestedMode;
  // External codec requests must precede loading the page; an existing page
  // reconnects with its own selected codec. Size/rate changes retain the page.
  if (newMode) await page.goto('about:blank');
  await api('/api/config/video', 'patch', video);
  if (newMode) {
    await api('/api/stream/mode', 'post', { mode });
    await page.goto(url);
    requestedMode = mode;
  }
}

async function webRtc(mode, height, fps) {
  const expectedHeight = height || 2160, expectedWidth = expectedHeight * 16 / 9;
  await configure(mode, { output: { height, fps } });
  await page.waitForFunction(([w, h]) => {
    const video = document.querySelector('video');
    return video?.videoWidth === w && video.videoHeight === h && video.readyState >= 2;
  }, [expectedWidth, expectedHeight], { timeout: 45000 });
  await page.waitForTimeout(1500);
  const sample = () => page.evaluate(async () => {
    const peer = window.scalingPeers.findLast(p => p.connectionState === 'connected');
    if (!peer) throw new Error('No connected WebRTC peer');
    const stats = [...(await peer.getStats()).values()];
    const videoStats = stats.find(s => s.type === 'inbound-rtp' && s.kind === 'video');
    const codec = stats.find(s => s.id === videoStats?.codecId);
    const bitmap = await createImageBitmap(document.querySelector('video'));
    try {
      return { time: performance.now(), frames: videoStats.framesDecoded,
        width: bitmap.width, height: bitmap.height, codec: codec?.mimeType,
        markers: window.scalingMarkers(bitmap) };
    } finally { bitmap.close(); }
  });
  const first = await sample(); verifyMarkers(first.markers);
  await page.waitForTimeout(4000);
  const last = await sample(); verifyMarkers(last.markers);
  assert.notEqual(first.markers[0].id, last.markers[0].id, 'Source content froze');
  const decodedFps = (last.frames - first.frames) * 1000 / (last.time - first.time);
  assert(decodedFps > fps * .9 && decodedFps < fps * 1.1, `Unexpected fps: ${decodedFps}`);
  assert(last.codec?.toLowerCase().endsWith(mode === 'h265' ? 'h265' : 'h264'), `Wrong negotiated codec: ${last.codec}`);
  console.log(JSON.stringify({ kind: 'webrtc', mode, output: { height, fps }, decodedFps,
    input: await inputState(), first, last }));
}

async function mjpeg(height, quality) {
  const expectedHeight = height || 2160, expectedWidth = expectedHeight * 16 / 9;
  await configure('mjpeg', { output: { height, fps: 30 }, quality });
  await page.waitForFunction(([w, h]) => [...document.images].some(image =>
    image.src.includes('/stream/mjpeg') && image.naturalWidth === w && image.naturalHeight === h),
  [expectedWidth, expectedHeight], { timeout: 30000 });
  const result = await page.evaluate(async ({ width, height }) => {
    const abort = new AbortController(), timer = setTimeout(() => abort.abort(), 15000);
    const decoder = new TextDecoder();
    let reader;
    try {
      const response = await fetch('/api/stream/mjpeg', { signal: abort.signal });
      if (!response.ok) throw new Error(`MJPEG HTTP ${response.status}`);
      reader = response.body.getReader();
      let pending = new Uint8Array(), frames = 0, first, last;
      const markers = [];
      while (frames < 90) {
        const next = await reader.read();
        if (next.done) throw new Error('MJPEG stream ended');
        const combined = new Uint8Array(pending.length + next.value.length);
        combined.set(pending); combined.set(next.value, pending.length); pending = combined;
        while (true) {
          let end = -1;
          for (let i = 0; i < pending.length - 3; i++) {
            if (pending[i] === 13 && pending[i+1] === 10 && pending[i+2] === 13 && pending[i+3] === 10) { end = i; break; }
          }
          if (end < 0) break;
          const header = decoder.decode(pending.subarray(0, end));
          const length = Number(header.match(/Content-Length:\s*(\d+)/i)?.[1]);
          if (!Number.isSafeInteger(length) || length <= 0 || length > 20 * 1024 * 1024)
            throw new Error('Invalid MJPEG part length');
          if (pending.length < end + 4 + length) break;
          const data = pending.slice(end + 4, end + 4 + length);
          pending = pending.slice(end + 4 + length);
          const now = performance.now(); first ??= now; last = now;
          if (frames % 30 === 0 || frames === 89) {
            const bitmap = await createImageBitmap(new Blob([data], { type: 'image/jpeg' }));
            try {
              if (bitmap.width !== width || bitmap.height !== height) throw new Error('Wrong JPEG dimensions');
              markers.push(window.scalingMarkers(bitmap));
            } finally { bitmap.close(); }
          }
          frames++;
          if (frames >= 90) break;
        }
      }
      return { frames, fps: (frames - 1) * 1000 / (last - first), markers };
    } finally { clearTimeout(timer); abort.abort(); if (reader) await reader.cancel().catch(() => {}); }
  }, { width: expectedWidth, height: expectedHeight });
  for (const markers of result.markers) verifyMarkers(markers);
  assert(new Set(result.markers.map(m => m[0].id)).size > 1, 'JPEG content froze');
  assert(result.fps > 25 && result.fps < 35, `Unexpected MJPEG cadence: ${result.fps}`);
  console.log(JSON.stringify({ kind: 'mjpeg', height, quality, input: await inputState(), ...result }));
}

try {
  await loginManager(page.context(), url);
  saved = { video: await api('/api/config/video'), mode: (await api('/api/stream/mode')).mode };
  const uu = await api('/api/config/uu-remote');
  if (uu.config.enabled) {
    assert(args.includes('--pause-idle-uu'), 'MJPEG requires pausing idle UU; pass --pause-idle-uu');
    assert.equal(uu.status.connection_count, 0, 'UU has an active connection');
    assert.equal(uu.status.sessions.length, 0, 'UU has an active session');
    uuPaused = true;
    await api('/api/config/uu-remote', 'patch', { enabled: false });
  }
  await page.goto(url);
  for (const [mode, height, fps] of [
    ['h265', 0, 60], ['h265', 1080, 60], ['h265', 720, 30], ['h265', 0, 60],
    ['h264', 1080, 60], ['h264', 720, 30], ['h264', 0, 60],
  ]) await webRtc(mode, height, fps);
  for (const [height, quality] of [[1080, 80], [720, 50], [0, 80]]) await mjpeg(height, quality);
  await webRtc('h265', 0, 60);
} finally {
  try {
    await page.goto('about:blank');
    try {
      if (saved) {
        await api('/api/config/video', 'patch', { output: saved.video.output, quality: saved.video.quality });
        await api('/api/stream/mode', 'post', { mode: saved.mode });
      }
    } finally {
      if (uuPaused) await api('/api/config/uu-remote', 'patch', { enabled: true });
    }
  } finally { await browser.close(); }
}
const deadline = Date.now() + 15000;
while (true) {
  const dma = execFileSync('ssh', ['vim4', 'sudo', '-n', 'cat', '/sys/kernel/debug/dma_buf/bufinfo'],
    { encoding: 'utf8', timeout: 5000 });
  if (dma.includes('Total 0 objects, 0 bytes')) break;
  assert(Date.now() < deadline, 'Capture DMA retained after closing viewer');
  await new Promise(resolve => setTimeout(resolve, 250));
}
console.log(JSON.stringify({ kind: 'complete', settingsRestored: true, idleDmaBytes: 0 }));
