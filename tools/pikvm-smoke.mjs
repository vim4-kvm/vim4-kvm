// PiKVM browser decoding and macOS USB input checks. Requires exclusive access.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate hardware access and pass --exclusive');
assert(process.env.PIKVM_USERNAME && process.env.PIKVM_PASSWORD, 'Set PIKVM_USERNAME and PIKVM_PASSWORD');
const url = process.env.PIKVM_URL || 'http://192.168.50.210:8080';
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
const context = await browser.newContext();
await context.addInitScript(() => {
  window.pikvmPeers = [];
  const Peer = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends Peer {
    constructor(...args) { super(...args); window.pikvmPeers.push(this); }
  };
});
const page = await context.newPage();
page.on('pageerror', error => console.error('Browser:', error.message));
page.on('console', message => { if (message.type() === 'error') console.error(message.text()); });
const api = async (path, method = 'GET') => {
  const result = await page.evaluate(async ({ path, method }) => {
    const response = await fetch('/api/' + path, { method });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }, { path, method });
  assert(result.ok, `${path}: ${JSON.stringify(result)}`);
  return result.result;
};
const pointer = () => execFileSync('osascript', ['-l', 'JavaScript', '-e',
  'ObjC.import("AppKit"); const p=$.NSEvent.mouseLocation; const f=$.NSScreen.screens.objectAtIndex(0).frame; [p.x/f.size.width,1-p.y/f.size.height].join(" ")'],
  { encoding: 'utf8' }).trim().split(' ').map(Number);
const move = ([x, y]) => api(`hid/events/send_mouse_move?to_x=${Math.round(x * 65535 - 32768)}&to_y=${Math.round(y * 65535 - 32768)}`, 'POST');
let original;
let sourceBrowser;
let mediaName;
let sound;
try {
  await page.goto(url + '/login');
  await page.locator('#user-input').fill(process.env.PIKVM_USERNAME);
  await page.locator('#passwd-input').fill(process.env.PIKVM_PASSWORD);
  await page.locator('#login-button').click();
  await page.waitForURL(url + '/');
  await page.locator('#apps a[href="./kvm/"]').click();
  await page.waitForURL(url + '/kvm/');
  await page.waitForFunction(() => document.querySelector('#stream-video')?.videoWidth > 0, null, { timeout: 60000 });
  const first = await page.$eval('#stream-video', video => video.getVideoPlaybackQuality().totalVideoFrames);
  await page.waitForTimeout(10000);
  const video = await page.$eval('#stream-video', video => ({
    width: video.videoWidth, height: video.videoHeight,
    frames: video.getVideoPlaybackQuality().totalVideoFrames,
    dropped: video.getVideoPlaybackQuality().droppedVideoFrames,
  }));
  assert(video.frames > first + 10, 'Video decoding did not advance');
  const soakSeconds = Number(process.argv.find(arg => arg.startsWith('--soak='))?.split('=')[1] || 0);
  if (soakSeconds) {
    const soak = await page.evaluate(async seconds => {
      const video = document.querySelector('#stream-video');
      const gaps = [];
      let last;
      let callback;
      const frame = now => {
        if (last !== undefined) gaps.push(now - last);
        last = now;
        callback = video.requestVideoFrameCallback(frame);
      };
      callback = video.requestVideoFrameCallback(frame);
      await new Promise(resolve => setTimeout(resolve, seconds * 1000));
      video.cancelVideoFrameCallback(callback);
      const stats = [];
      for (const peer of window.pikvmPeers) {
        for (const report of (await peer.getStats()).values()) {
          if (report.type === 'inbound-rtp' && report.kind === 'video') stats.push(report);
        }
      }
      gaps.sort((a, b) => a - b);
      return { seconds, callbacks: gaps.length, maxGapMs: gaps.at(-1), p99GapMs: gaps[Math.floor(gaps.length * .99)],
        gapsOver250ms: gaps.filter(gap => gap > 250), stats };
    }, soakSeconds);
    console.log('SOAK', JSON.stringify(soak));
  }
  const snapshot = await page.evaluate(async () => {
    const response = await fetch('/api/streamer/snapshot');
    return { status: response.status, signature: [...new Uint8Array(await response.arrayBuffer()).slice(0, 2)] };
  });
  assert(snapshot.status === 200 && snapshot.signature.join(',') === '255,216', 'JPEG snapshot missing');
  const rtc = await page.evaluate(async () => {
    const result = [];
    for (const peer of window.pikvmPeers) {
      if (peer.connectionState === 'connected') {
        const stats = await peer.getStats();
        for (const stat of stats.values()) {
          if (stat.type === 'inbound-rtp') result.push({ kind: stat.kind, bytes: stat.bytesReceived,
            frames: stat.framesDecoded, packetsLost: stat.packetsLost, codec: stats.get(stat.codecId)?.mimeType });
        }
      }
    }
    return result;
  });
  assert(rtc.some(stat => stat.kind === 'video' && stat.frames > 0), 'No Janus WebRTC video');
  if (process.env.PIKVM_EXPECT_CODEC) {
    assert(rtc.some(stat => stat.kind === 'video' && stat.codec === process.env.PIKVM_EXPECT_CODEC), 'Unexpected video codec');
  }
  const extra = {};
  if (process.argv.includes('--motion')) {
    sourceBrowser = await chromium.launch({ channel: 'chrome', headless: false });
    const source = await sourceBrowser.newPage();
    await source.setContent('<body style="margin:0"><canvas width="1200" height="800"></canvas><script>const c=document.querySelector("canvas").getContext("2d");setInterval(()=>{const t=Date.now();c.fillStyle=t%1000<500?"#ff0033":"#00cc66";c.fillRect(0,0,1200,800);c.fillStyle="white";c.font="64px monospace";c.fillText("VIM4 motion "+t,30,150)},100)</script>');
    const hashes = await page.evaluate(async () => {
      const video = document.querySelector('#stream-video');
      const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 36;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      const hashes = [];
      for (let i = 0; i < 8; ++i) {
        await new Promise(resolve => setTimeout(resolve, 400));
        ctx.drawImage(video, 0, 0, 64, 36);
        let hash = 0;
        for (const value of ctx.getImageData(0, 0, 64, 36).data) hash = (hash * 31 + value) | 0;
        hashes.push(hash);
      }
      return hashes;
    });
    assert(new Set(hashes).size > 2, 'Decoded image content did not change');
    extra.motionHashes = hashes;
    console.log('PASS: decoded motion', hashes);
    await sourceBrowser.close(); sourceBrowser = null;
  }
  if (process.argv.includes('--audio')) {
    assert(process.env.PIKVM_TEST_AUDIO, 'Set PIKVM_TEST_AUDIO to a non-silent WAV played through HDMI');
    await page.evaluate(() => {
      const toggle = document.querySelector('#stream-multimedia-switch');
      if (!toggle.checked) toggle.click();
      document.querySelector('#stream-video').muted = true;
    });
    await page.waitForFunction(() => document.querySelector('#stream-video')?.srcObject?.getAudioTracks().length > 0);
    sound = spawn('afplay', [process.env.PIKVM_TEST_AUDIO], { stdio: 'ignore' });
    const peak = await page.evaluate(async () => {
      const video = document.querySelector('#stream-video'); video.muted = true;
      const audio = new AudioContext(); await audio.resume();
      const source = audio.createMediaStreamSource(new MediaStream(video.srcObject.getAudioTracks()));
      const analyser = audio.createAnalyser(); source.connect(analyser);
      const values = new Float32Array(analyser.fftSize); let peak = 0;
      for (let i = 0; i < 30; ++i) {
        await new Promise(resolve => setTimeout(resolve, 100));
        analyser.getFloatTimeDomainData(values);
        for (const value of values) peak = Math.max(peak, Math.abs(value));
      }
      source.disconnect(); await audio.close(); return peak;
    });
    sound.kill(); sound = null;
    assert(peak > 0.001, `Decoded audio is silent: peak=${peak}`);
    extra.audioPeak = peak;
    console.log('PASS: decoded HDMI audio peak', peak);
  }
  if (process.argv.includes('--usb')) {
    original = pointer();
    for (const target of [[0.25, 0.25], [0.7, 0.6]]) {
      await move(target);
      await page.waitForTimeout(500);
      const actual = pointer();
      assert(actual.every((value, i) => Math.abs(value - target[i]) < 0.02), `Pointer ${actual}, expected ${target}`);
    }
    await api('hid/events/send_key?key=ShiftLeft&state=true', 'POST');
    try {
      await page.waitForTimeout(250);
      const flags = Number(execFileSync('osascript', ['-l', 'JavaScript', '-e',
        'ObjC.import("AppKit"); $.NSEvent.modifierFlags'], { encoding: 'utf8' }).trim());
      assert(flags & (1 << 17), 'Host did not receive Shift');
    } finally {
      await api('hid/events/send_key?key=ShiftLeft&state=false', 'POST');
    }
  }
  if (process.argv.includes('--media')) {
    assert(process.env.PIKVM_TEST_ISO, 'Set PIKVM_TEST_ISO to the PIKVM_TEST validation ISO');
    assert.equal((await api('msd')).drive?.connected, false, 'Existing virtual media must be ejected first');
    mediaName = `vim4-smoke-${Date.now()}.iso`;
    const uploaded = await page.evaluate(async ({ name, data }) => {
      const response = await fetch('/api/msd/write?image=' + encodeURIComponent(name), { method: 'POST',
        body: Uint8Array.from(atob(data), char => char.charCodeAt(0)) });
      return response.json();
    }, { name: mediaName, data: readFileSync(process.env.PIKVM_TEST_ISO).toString('base64') });
    assert(uploaded.ok, JSON.stringify(uploaded));
    for (let i = 0; i < 20; ++i) {
      if ((await api('msd')).storage?.images?.[mediaName]) break;
      await page.waitForTimeout(250);
    }
    await api(`msd/set_params?image=${encodeURIComponent(mediaName)}&cdrom=true&rw=false`, 'POST');
    await api('msd/set_connected?connected=true', 'POST');
    let marker;
    for (let i = 0; i < 30; ++i) {
      try { marker = readFileSync('/Volumes/PIKVM_TEST/readme.txt', 'utf8'); break; } catch {}
      await page.waitForTimeout(500);
    }
    assert.equal(marker?.trim(), 'PiKVM VIM4 virtual media validation', 'USB host could not read the ISO');
    if (process.argv.includes('--switch-guard')) {
      let rejection;
      try {
        execFileSync('ssh', [process.env.VIM4_SSH || 'vim4',
          'sudo -n /usr/libexec/vim4-manager-helper select nanokvm'], { stdio: 'pipe' });
      } catch (error) { rejection = error.stderr?.toString(); }
      assert(rejection?.includes('Eject the PiKVM virtual disk'), 'Manager must refuse a switch with mounted media');
      assert((await api('msd')).drive.connected, 'Rejected switch changed the running application');
      extra.mountedMediaSwitchGuard = 'passed';
    }
    execFileSync('diskutil', ['eject', '/Volumes/PIKVM_TEST'], { stdio: 'pipe' });
    for (let i = 0; i < 20 && (await api('msd')).drive?.connected; ++i) await page.waitForTimeout(250);
    if ((await api('msd')).drive?.connected) await api('msd/set_connected?connected=false', 'POST');
    await api('msd/remove?image=' + encodeURIComponent(mediaName), 'POST');
    mediaName = null;
    extra.virtualMedia = 'host read and eject passed';
  }
  if (process.argv.includes('--mjpeg')) {
    await page.evaluate(() => document.querySelector('input[name="stream-mode-radio"][value="mjpeg"]').click());
    await page.waitForFunction(({ width, height }) => {
      const image = document.querySelector('#stream-image');
      return !image.classList.contains('hidden') && image.naturalWidth === width && image.naturalHeight === height;
    }, video);
    extra.mjpeg = await page.$eval('#stream-image', image => ({ width: image.naturalWidth, height: image.naturalHeight }));
    await page.evaluate(() => document.querySelector('input[name="stream-mode-radio"][value="janus"]').click());
    await page.waitForFunction(() => document.querySelector('#stream-video').videoWidth > 0);
    const before = await page.$eval('#stream-video', element => element.getVideoPlaybackQuality().totalVideoFrames);
    await page.waitForFunction(before => document.querySelector('#stream-video').getVideoPlaybackQuality().totalVideoFrames > before + 10, before);
  }
  if (process.argv.includes('--settings')) {
    const saved = (await api('streamer')).params;
    try {
      await api('streamer/set_params?desired_fps=30&h264_bitrate=8000&quality=70', 'POST');
      await page.waitForFunction(async () => {
        const state = (await (await fetch('/api/streamer')).json()).result;
        return state.streamer?.source?.desired_fps === 30 && state.streamer?.h264?.bitrate === 8000;
      });
      await page.reload();
      await page.waitForFunction(() => document.querySelector('#stream-video')?.getVideoPlaybackQuality().totalVideoFrames > 30);
      extra.settingsAndReload = 'passed';
    } finally {
      await api('streamer/set_params?' + new URLSearchParams(saved), 'POST');
    }
  }
  await page.screenshot({ path: 'logs/pikvm/browser.png' });
  console.log(JSON.stringify({ video, framesInTenSeconds: video.frames - first, rtc,
    jpeg: 'passed', usb: original ? 'passed' : 'not requested', ...extra }, null, 2));
} finally {
  sound?.kill();
  if (sourceBrowser) await sourceBrowser.close();
  try {
    if (mediaName) {
      try { execFileSync('diskutil', ['eject', '/Volumes/PIKVM_TEST'], { stdio: 'pipe' }); } catch {}
      if ((await api('msd')).drive?.connected) await api('msd/set_connected?connected=false', 'POST');
    }
    if (original) await move(original);
  } finally { await browser.close(); }
}
