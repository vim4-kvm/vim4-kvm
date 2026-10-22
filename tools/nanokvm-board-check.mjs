// Exclusive NanoKVM EDID changes with a viewer kept open; restores the table.
import assert from 'node:assert/strict';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Requires exclusive HDMI access');
const url = process.env.NANOKVM_URL || 'http://192.168.50.210:8080';
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }), headless: true });
const context = await browser.newContext();
const page = await context.newPage();
let saved;
async function api(method, edid) {
  const response = await context.request.fetch(url + '/api/vm/edid', {
    method, headers: { Origin: url }, ...(edid ? { data: { edid } } : {}), timeout: 60000,
  });
  assert(response.ok(), `EDID HTTP ${response.status()}`);
  const result = await response.json();
  assert.equal(result.code, 0, result.msg);
  return result.data;
}
try {
  await loginManager(context, url);
  saved = (await api('GET')).edid;
  assert(['RTK-CONTROL', 'VIM4-4K60', 'VIM4-1080P60', 'VIM4-1080P60-SDR8'].includes(saved),
    'Preserve a custom EDID');
  await page.addInitScript(() => localStorage.setItem('nano-kvm-vide-mode', 'h264'));
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('video')?.videoHeight > 0, null, { timeout: 45000 });
  const initialHeight = await page.$eval('video', video => video.videoHeight);
  for (const [preset, height] of [['VIM4-1080P60-SDR8', 1080], ['RTK-CONTROL', 2160]]) {
    await api('POST', preset);
    assert.equal((await api('GET')).edid, preset);
    await page.waitForFunction(height => document.querySelector('video')?.videoHeight === height,
      Math.min(height, initialHeight), { timeout: 45000 });
    const first = await page.$eval('video', video => video.getVideoPlaybackQuality().totalVideoFrames);
    await page.waitForTimeout(2000);
    const last = await page.$eval('video', video => ({ width: video.videoWidth, height: video.videoHeight,
      frames: video.getVideoPlaybackQuality().totalVideoFrames }));
    assert(last.frames > first + 20, 'Existing NanoKVM viewer did not recover');
    console.log(JSON.stringify({ test: 'nanokvm-native-edid', preset, video: last, advanced: last.frames - first }));
  }
} finally {
  try {
    await page.goto('about:blank');
    if (saved) await api('POST', saved);
  } finally { await browser.close(); }
}
