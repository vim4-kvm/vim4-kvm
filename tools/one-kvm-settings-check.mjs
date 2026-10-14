// Exclusive hardware regression: restores all changed settings, including EDID/HDR.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
const username = process.env.ONEKVM_USERNAME, password = process.env.ONEKVM_PASSWORD;
assert(username && password, 'Set ONEKVM_USERNAME and ONEKVM_PASSWORD');
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const context = await browser.newContext();
const control = await context.newPage();
const view = await context.newPage();
await view.addInitScript(() => {
  window.testPeers = [];
  const Original = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends Original {
    constructor(...args) { super(...args); window.testPeers.push(this); }
  };
});
const api = (path, method = 'GET', body) => control.evaluate(async ({ path, method, body }) => {
  const r = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const result = await r.json();
  if (!r.ok) throw new Error(path + ': ' + r.status + ' ' + JSON.stringify(result));
  return result;
}, { path, method, body });
let saved;
try {
  await control.goto(url + '/api/setup');
  await api('auth/login', 'POST', { username, password });
  saved = { video: await api('config/video'), stream: await api('config/stream'),
    mode: await api('stream/mode'), board: await api('vim4/video') };
  assert(['VIM4-4K60', 'VIM4-1080P60'].includes(saved.board.edid), 'Preserve custom EDID; test requires a built-in preset');
  const input = await api('video/input-status?device=/dev/video_cap');
  assert.equal(input.state, 'locked');
  assert(input.width > 0 && input.fps > 0);
  console.log(JSON.stringify({ input, board: saved.board }));

  for (const scenario of [
    { mode: 'h264', height: 1080, fps: 30, quality: 80, bitrate: 4000 },
    { mode: 'h265', height: 720, fps: 15, quality: 80, bitrate: 2000 },
    { mode: 'mjpeg', height: 1080, fps: 10, quality: 35, bitrate: 2000 },
    { mode: 'mjpeg', height: 1080, fps: 10, quality: 90, bitrate: 2000 },
    { mode: 'h264', height: 0, fps: 0, quality: 80, bitrate: 8000 },
  ]) {
    await view.goto('about:blank');
    await api('config/video', 'PATCH', { output: { height: scenario.height, fps: scenario.fps }, quality: scenario.quality });
    await api('stream/bitrate', 'POST', { bitrate_preset: { type: 'Custom', value: scenario.bitrate } });
    await api('stream/mode', 'POST', { mode: scenario.mode });
    if (process.argv.includes('--restart') && scenario.mode === 'h264' && scenario.height === 1080) {
      execFileSync('ssh', ['vim4', 'sudo systemctl restart one-kvm'], { stdio: 'pipe' });
      for (let attempt = 0; ; attempt++) {
        try { await control.goto(url + '/api/setup'); break; }
        catch (error) {
          if (attempt >= 20) throw error;
          await control.waitForTimeout(250);
        }
      }
      await api('auth/login', 'POST', { username, password });
      const persisted = await api('config/video');
      assert.deepEqual(persisted.output, { height: scenario.height, fps: scenario.fps });
      assert.equal(persisted.quality, scenario.quality);
    }
    await view.goto(url);
    const expectedHeight = scenario.height || input.height;
    if (scenario.mode === 'mjpeg') {
      await view.waitForFunction(height => [...document.images].some(i => i.src.includes('/stream/mjpeg') && i.naturalHeight === height), expectedHeight, { timeout: 30000 });
      const jpeg = await control.evaluate(async () => {
        const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 10000);
        try {
          const r = await fetch('/api/stream/mjpeg', { signal: abort.signal });
          const reader = r.body.getReader();
          let previous = 0, length = 0, inFrame = false;
          const frames = [];
          while (frames.length < 5) {
            const { value, done } = await reader.read();
            if (done) throw new Error('MJPEG ended');
            for (const b of value) {
              if (previous === 255 && b === 216) { inFrame = true; length = 1; }
              if (inFrame) length++;
              if (inFrame && previous === 255 && b === 217) { frames.push(length); inFrame = false; }
              previous = b;
            }
          }
          await reader.cancel();
          return frames;
        } finally { clearTimeout(timeout); abort.abort(); }
      });
      console.log(JSON.stringify({ scenario, jpegBytes: jpeg }));
    } else {
      await view.waitForFunction(height => document.querySelector('video')?.videoHeight === height, expectedHeight, { timeout: 45000 });
      const sample = () => view.evaluate(async () => {
        for (const peer of window.testPeers.toReversed()) {
          if (peer.connectionState !== 'connected') continue;
          for (const s of (await peer.getStats()).values()) if (s.type === 'inbound-rtp' && s.kind === 'video')
            return { frames: s.framesDecoded, time: s.timestamp, width: s.frameWidth, height: s.frameHeight };
        }
      });
      const first = await sample();
      await view.waitForTimeout(5000);
      const last = await sample();
      const fps = (last.frames - first.frames) * 1000 / (last.time - first.time);
      assert(fps >= (scenario.fps || input.fps) * 0.75 && fps <= (scenario.fps || input.fps) * 1.15, 'Unexpected decoded FPS: ' + fps);
      console.log(JSON.stringify({ scenario, decoded: last, fps }));
      if (scenario.mode === 'h264' && scenario.height === 1080) {
        await api('config/video', 'PATCH', { output: { height: 720, fps: 30 } });
        await view.waitForFunction(() => document.querySelector('video')?.videoHeight === 720, {}, { timeout: 30000 });
        await api('config/video', 'PATCH', { output: { height: 1080, fps: 30 } });
        await view.waitForFunction(() => document.querySelector('video')?.videoHeight === 1080, {}, { timeout: 30000 });
        console.log('Output changes recovered in the existing viewer');
      }
    }
    assert.deepEqual((await api('config/video')).output, { height: scenario.height, fps: scenario.fps });
  }
  // Changing the curve while SDR is active must not interrupt the HDMI service.
  assert.equal((await api('vim4/video', 'POST', { action: 'hdr', white: 220, peak: 1200 })).white, 220);
  if (process.argv.includes('--edid')) {
    for (const preset of ['VIM4-1080P60', 'VIM4-4K60']) {
      assert.equal((await api('vim4/video', 'POST', { action: 'edid', preset })).edid, preset);
      await view.waitForTimeout(6000);
      assert.equal((await api('video/input-status?device=/dev/video_cap')).state, 'locked');
    }
  }
  await view.getByRole('button', { name: /^(Video|视频采集|视频)$/ }).click();
  await view.getByTestId('vim4-video-settings').waitFor();
  await view.getByTestId('vim4-video-settings').locator('fieldset').waitFor({ state: 'visible' });
  await view.waitForTimeout(500);
  await view.locator('#vim4-quality').fill('70');
  await view.getByTestId('vim4-video-settings').locator('form').first().getByRole('button').click();
  await control.waitForFunction(async () => (await (await fetch('/api/config/video')).json()).quality === 70);
  await view.screenshot({ path: 'logs/one-kvm-settings/controls.png', fullPage: true });
  console.log('VIM4 settings controls rendered');
} catch (error) {
  console.error('Settings regression failed:', error);
  throw error;
} finally {
  try {
    await view.goto('about:blank');
    if (saved) {
      // A failed candidate may have restarted and invalidated its sessions.
      await control.goto(url + '/api/setup');
      await api('auth/login', 'POST', { username, password });
      await api('config/video', 'PATCH', { output: saved.video.output, quality: saved.video.quality });
      await api('stream/bitrate', 'POST', { bitrate_preset: saved.stream.bitrate_preset });
      await api('stream/mode', 'POST', { mode: saved.mode.mode });
      await api('vim4/video', 'POST', { action: 'hdr', white: saved.board.white, peak: saved.board.peak });
      if (process.argv.includes('--edid') && ['VIM4-4K60', 'VIM4-1080P60'].includes(saved.board.edid))
        await api('vim4/video', 'POST', { action: 'edid', preset: saved.board.edid });
    }
  } finally { await browser.close(); }
}
