// Requires exclusive board access. Exercises the manager's real selection API
// while the previous browser viewer remains connected; finishes on NanoKVM.
// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node tools/kvm-switch-check.mjs --exclusive [manager URL]
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
if (!args.includes('--exclusive')) throw new Error('Coordinate board access and pass --exclusive');
const manager = args.find((arg) => arg !== '--exclusive') || 'http://192.168.50.210';
const appURL = new URL(manager);
appURL.port = '8080';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
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
try {
  for (const app of ['nanokvm', 'jetkvm', 'nanokvm', 'jetkvm', 'nanokvm']) {
    const begin = Date.now();
    const response = await page.request.post(`${manager}/api/select`, { data: { app }, timeout: 60000 });
    assert(response.ok(), `selection failed: ${await response.text()}`);
    selected = app;
    appURL.searchParams.set('kvm', app);
    const status = await (await page.request.get(`${manager}/api/status`)).json();
    assert.equal(status.active, app);
    for (const entry of status.apps) {
      assert.equal(entry.unit.active, entry.id === app ? 'active' : 'inactive');
      assert.equal(entry.unit.enabled, entry.id === app ? 'enabled' : 'disabled');
    }
    let loaded = false;
    for (let attempt = 0; attempt < 20; attempt++) {
      try { await page.goto(appURL.href, { timeout: 10000 }); loaded = true; break; }
      catch { await new Promise((resolve) => setTimeout(resolve, 500)); }
    }
    assert(loaded, 'application HTTP server did not become ready');
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
  if (selected && selected !== 'nanokvm') {
    const restored = await page.request.post(`${manager}/api/select`, { data: { app: 'nanokvm' }, timeout: 60000 });
    if (!restored.ok()) console.error('Failed to restore NanoKVM:', await restored.text());
  }
  await browser.close();
}
