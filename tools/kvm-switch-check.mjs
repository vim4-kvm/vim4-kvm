// Requires exclusive board access. Exercises the manager's real selection API
// while the previous browser viewer remains connected; restores the initial selection.
// Set MANAGER_PASSWORD (and MANAGER_USERNAME, default admin) for the manager login.
// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node tools/kvm-switch-check.mjs --exclusive [manager URL]
import assert from 'node:assert/strict';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
if (!args.includes('--exclusive')) throw new Error('Coordinate board access and pass --exclusive');
const manager = args.find((arg) => arg !== '--exclusive') || 'http://192.168.50.210';
const appURL = new URL(manager);
appURL.port = '8080';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext();
const page = await context.newPage();
const control = await context.newPage();
await loginManager(context, manager);
await control.goto(manager);
const managerAPI = (path, body) => control.evaluate(async ({ path, body }) => {
  const response = await fetch(path, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : {});
  if (!response.ok) throw new Error(path + ' HTTP ' + response.status + ': ' + await response.text());
  return response.json();
}, { path, body });
await page.addInitScript(() => {
  window.switchPeers = [];
  const Original = window.RTCPeerConnection;
  window.RTCPeerConnection = class extends Original {
    constructor(...args) { super(...args); window.switchPeers.push(this); }
  };
});
const sample = () => page.evaluate(async () => {
  for (const peer of window.switchPeers) {
    for (const stat of (await peer.getStats()).values()) {
      if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
        return { timestamp: stat.timestamp, frames: stat.framesDecoded, dropped: stat.framesDropped,
          lost: stat.packetsLost, width: stat.frameWidth, height: stat.frameHeight,
          state: peer.connectionState };
      }
    }
  }
  return null;
});
let selected;
const initial = await managerAPI('/api/status');
const hasOneKVM = initial.apps.some(entry => entry.id === 'onekvm' && entry.unit.loaded);
const sequence = hasOneKVM
  ? ['onekvm', 'nanokvm', 'jetkvm', 'onekvm', 'jetkvm', 'nanokvm']
  : ['nanokvm', 'jetkvm', 'nanokvm', 'jetkvm', 'nanokvm'];
try {
  for (const app of sequence) {
    const begin = Date.now();
    await managerAPI('/api/select', { app });
    selected = app;
    appURL.searchParams.set('kvm', app);
    const status = await managerAPI('/api/status');
    assert.equal(status.active, app);
    for (const entry of status.apps) {
      assert.equal(entry.unit.active, entry.id === app ? 'active' : 'inactive');
      assert.equal(entry.unit.enabled, entry.id === app ? 'enabled' : 'disabled');
    }
    let loaded = false;
    for (let attempt = 0; attempt < 20; attempt++) {
      try {
        const response = await page.goto(app === 'onekvm' ? new URL('/api/setup', appURL).href : appURL.href, { timeout: 10000 });
        if (!response?.ok()) throw new Error('Application not ready');
        if (app === 'onekvm') assert((await response.json()).initialized, 'One-KVM is not initialized');
        loaded = true;
        break;
      }
      catch { await new Promise((resolve) => setTimeout(resolve, 500)); }
    }
    assert(loaded, 'application HTTP server did not become ready');
    if (app === 'onekvm') {
      await page.goto(appURL.href);
    }
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, { timeout: 45000 });
    const firstFrameMs = Date.now() - begin;
    const start = await sample();
    assert(start, 'missing inbound video');
    await page.waitForTimeout(10000);
    const end = await sample();
    assert.equal(end.state, 'connected');
    assert(end.frames > start.frames, 'video stalled');
    console.log(JSON.stringify({ app, firstFrameMs, width: end.width, height: end.height,
      decoded: end.frames - start.frames,
      fps: (end.frames - start.frames) * 1000 / (end.timestamp - start.timestamp),
      dropped: end.dropped - start.dropped, lost: end.lost - start.lost }));
  }
} finally {
  if (selected && selected !== initial.active) {
    await managerAPI('/api/select', { app: initial.active });
  }
  await browser.close();
}
