// Exclusive 7.x -> 5.15 -> 7.x integration check. Reboots the board twice.
// Uses private SSH forwards, the real manager confirmation, One-KVM settings
// and disposable image uploads. Never mounts or overwrites an existing image.
// MANAGER_PASSWORD, PLAYWRIGHT_MODULE, VIM4_TEST_CHROME; --exclusive --reboot.
import assert from 'node:assert/strict';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import { execFileSync, spawn } from 'node:child_process';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive') && process.argv.includes('--reboot'),
  'Requires exclusive access and explicit --reboot');
const manager = 'http://127.0.0.1:18480';
const app = 'http://127.0.0.1:18481';
const board = process.env.VIM4_SSH_HOST || 'vim4';
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel:'chrome' }), headless:true });
const context = await browser.newContext();
const page = await context.newPage();
let forward, savedVideo, savedMode, initialApp;
const images = [];
const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function connect() {
  if (forward) { forward.kill(); await delay(250); }
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    if (!forward || forward.exitCode !== null || forward.killed) {
      forward = spawn('ssh', ['-N', '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=5',
        '-o', 'ServerAliveInterval=2', '-o', 'ServerAliveCountMax=2',
        '-L', '127.0.0.1:18480:127.0.0.1:80', '-L', '127.0.0.1:18481:127.0.0.1:8080', board],
      {stdio:'ignore'});
    }
    try {
      const r = await context.request.get(manager + '/__vim4/api/auth/state', {timeout:2000});
      if (r.ok()) { await loginManager(context, manager); return; }
    } catch {}
    await delay(1500);
  }
  throw new Error('Board did not restore its manager within 180 seconds');
}
async function api(origin, path, method='GET', data) {
  const response = await context.request.fetch(origin + path, {
    method, data, headers:{Origin:origin}, timeout:90000,
  });
  assert(response.ok(), `${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}
async function waitApp() {
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    try { if ((await api(app,'/api/setup')).initialized) return; } catch {}
    await delay(1000);
  }
  throw new Error('One-KVM did not restore its application API');
}
async function upload() {
  const name = `kernel-compat-${randomUUID()}.img`;
  const payload = randomBytes(65536);
  const response = await context.request.post(app + '/api/msd/images', {
    headers:{Origin:app}, multipart:{file:{name,mimeType:'application/octet-stream',buffer:payload}},
  });
  assert(response.ok(), await response.text());
  const info = await response.json();
  assert.equal(info.name, name);
  images.push({id:info.id,name,size:payload.length,sha:createHash('sha256').update(payload).digest('hex')});
  console.log(JSON.stringify({test:'temporary-image-created',...images.at(-1)}));
}
async function verifyImages() {
  for (const expected of images) {
    const info = await api(app, '/api/msd/images/' + encodeURIComponent(expected.id));
    assert.equal(info.name, expected.name); assert.equal(info.size, expected.size);
    assert.match(expected.name, /^kernel-compat-[a-f0-9-]+\.img$/);
    const hash = execFileSync('ssh', [board,'sudo','-n','sha256sum','--',
      '/var/lib/one-kvm/msd/images/' + expected.name], {encoding:'utf8',timeout:10000}).split(/\s/)[0];
    assert.equal(hash, expected.sha);
  }
}
async function verifyRuntime(prefix, height) {
  const deadline = Date.now() + 90000;
  let state;
  while (Date.now() < deadline) {
    state = await api(manager, '/api/status');
    if (state.active === 'onekvm' && state.hardware.hdmi.signal) break;
    await delay(1500);
  }
  assert(state.hardware.kernel.startsWith(prefix));
  const failed = execFileSync('ssh', [board,'systemctl','--failed','--no-legend','--plain'],
    {encoding:'utf8',timeout:10000}).trim();
  assert.equal(failed,'','Kernel boot left failed services: ' + failed);
  assert.equal(state.active,'onekvm');
  assert(state.hardware.hdmi.signal);
  await waitApp();
  assert.equal((await api(app,'/api/config/video')).output.height,height);
  await verifyImages();
  await page.goto(app);
  await page.waitForFunction(height => document.querySelector('video')?.videoHeight === height,
    height, {timeout:60000});
  const initial = await page.$eval('video', video => video.getVideoPlaybackQuality().totalVideoFrames);
  await delay(2500);
  const end = await page.$eval('video', video => ({width:video.videoWidth,height:video.videoHeight,
    frames:video.getVideoPlaybackQuality().totalVideoFrames}));
  assert(end.frames > initial + 10);
  console.log(JSON.stringify({test:'kernel-data',running:state.hardware.kernel,
    video:end,failedUnits:0,sharedImageHashes:images.map(image => image.sha)}));
}
async function reboot(id) {
  await page.goto(manager + '/#updates');
  const state = await api(manager,'/api/kernel');
  const index = state.kernels.findIndex(kernel => kernel.id === id);
  assert(index >= 0 && state.kernels[index].available);
  await page.getByRole('button',{name:'选择并重启'}).nth(index).click();
  const response = page.waitForResponse(r => r.url() === manager + '/api/kernel' && r.request().method() === 'POST');
  await page.getByRole('button',{name:'确认重启',exact:true}).click();
  const result = await response;
  assert.deepEqual(result.request().postDataJSON(),{id,reboot:true});
  assert.equal(result.status(),200,await result.text());
  console.log(JSON.stringify({test:'kernel-switch-request',id,through:'manager-confirmation'}));
  await delay(5000);
  await connect();
}
async function checkApplications() {
  if (!process.argv.includes('--switch-apps')) return;
  await page.goto('about:blank');
  const script = new URL('./kvm-switch-check.mjs',import.meta.url).pathname;
  await new Promise((resolve,reject) => {
    const child = spawn(process.execPath,[script,'--exclusive',manager], {
      env:{...process.env,VIM4_KVM_URL:app},stdio:'inherit',
    });
    child.once('error',reject);
    child.once('exit',(code,signal) => code === 0 ? resolve() : reject(new Error(`Application cycle failed: ${code ?? signal}`)));
  });
  await waitApp();
}
try {
  await connect();
  const initial = await api(manager,'/api/status');
  assert(initial.hardware.kernel.startsWith('7.'));
  assert(!initial.media.inserted,'Safely eject existing media before testing');
  initialApp = initial.active;
  await api(manager,'/api/select','POST',{app:'onekvm'});
  await waitApp();
  savedVideo = await api(app,'/api/config/video');
  savedMode = await api(app,'/api/stream/mode');
  console.log(JSON.stringify({test:'kernel-settings-baseline',app:initialApp,
    output:savedVideo.output,mode:savedMode.mode}));
  await api(app,'/api/stream/mode','POST',{mode:'h264'});
  await api(app,'/api/config/video','PATCH',{output:{height:1080,fps:30}});
  await upload();
  await reboot('vendor');
  await verifyRuntime('5.15.',1080);
  await checkApplications();
  await page.goto('about:blank');
  await api(app,'/api/config/video','PATCH',{output:{height:720,fps:30}});
  await upload();
  await reboot('mainline');
  await verifyRuntime('7.',720);
  await checkApplications();
} finally {
  try {
    await page.goto('about:blank');
    if (savedVideo) {
      await waitApp();
      await api(app,'/api/config/video','PATCH',{output:savedVideo.output});
    }
    if (savedMode) await api(app,'/api/stream/mode','POST',{mode:savedMode.mode});
    for (const image of images) await api(app,'/api/msd/images/' + encodeURIComponent(image.id),'DELETE');
    if (initialApp && initialApp !== 'onekvm') await api(manager,'/api/select','POST',{app:initialApp});
  } finally { await browser.close(); forward?.kill(); }
}
