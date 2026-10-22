// Exclusive native board controls: live EDID changes and HDR curve restoration.
import assert from 'node:assert/strict';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'),'Requires exclusive HDMI access');
const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? {executablePath:process.env.VIM4_TEST_CHROME} : {channel:'chrome'}),headless:true });
const context = await browser.newContext();
const control = await context.newPage(), view = await context.newPage();
let saved, mode;
async function api(path,method='GET',data) {
  const response = await context.request.fetch(url + '/api/' + path,{
    method,headers:{Origin:url},...(data === undefined ? {} : {data}),timeout:60000,
  });
  assert(response.ok(),`${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}
async function frames(height) {
  await view.waitForFunction(height => document.querySelector('video')?.videoHeight === height,height,{timeout:45000});
  const first = await view.$eval('video',video => video.getVideoPlaybackQuality().totalVideoFrames);
  await view.waitForTimeout(1500);
  const last = await view.$eval('video',video => video.getVideoPlaybackQuality().totalVideoFrames);
  assert(last > first + 10,'Existing viewer did not resume');
  return last-first;
}
try {
  await loginManager(context,url);
  saved = await api('vim4/video'); mode = await api('stream/mode');
  assert(['RTK-CONTROL','VIM4-4K60','VIM4-1080P60','VIM4-1080P60-SDR8'].includes(saved.edid),'Preserve a custom EDID');
  await api('stream/mode','POST',{mode:'h264'});
  await control.goto(url + '/api/setup'); await view.goto(url);
  const originalInput = await api('video/input-status?device=/dev/video_cap');
  await frames(originalInput.height);
  const curve = await api('vim4/video','POST',{action:'hdr',white:220,peak:1200});
  assert.equal(curve.white,220); assert.equal(curve.peak,1200);
  for (const [preset,height] of [['VIM4-1080P60-SDR8',1080],['VIM4-4K60',2160],['RTK-CONTROL',2160]]) {
    const changed = await api('vim4/video','POST',{action:'edid',preset});
    assert.equal(changed.edid,preset);
    console.log(JSON.stringify({test:'native-board-change',preset,board:changed}));
    const advanced = await frames(height);
    const input = await api('video/input-status?device=/dev/video_cap');
    assert.equal(input.state,'locked'); assert.equal(input.height,height);
    console.log(JSON.stringify({test:'native-board-control',preset,input,advanced,board:changed}));
  }
} finally {
  try {
    await view.goto('about:blank');
    if (saved) {
      await api('vim4/video','POST',{action:'hdr',white:saved.white,peak:saved.peak});
      await api('vim4/video','POST',{action:'edid',preset:saved.edid});
    }
    if (mode) await api('stream/mode','POST',{mode:mode.mode});
  } finally { await browser.close(); }
}
