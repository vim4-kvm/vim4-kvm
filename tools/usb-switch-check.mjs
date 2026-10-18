import { loginManager } from './manager-login.mjs';
// Exercise the application USB relink paths while its original viewer holds HID.
// Pre-upload a disposable ISO. Requires an idle gadget with NCM, no microphone/media.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const [url, image, exclusive] = process.argv.slice(2);
if (!url || !image || exclusive !== '--exclusive') {
  throw new Error('Usage: usb-switch-check.mjs URL BOARD_ISO_PATH --exclusive');
}
const browser = await chromium.launch({ channel: 'chrome', headless: true });
let page;
let started = false;
async function api(path, body) {
  return page.evaluate(async ({ path, body }) => {
    const response = await fetch('/api/' + path, body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || result.code !== 0) throw new Error(JSON.stringify(result));
    return result.data;
  }, { path, body });
}
try {
  page = await browser.newPage();
  await loginManager(page.context(), url);
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0);
  const initial = await api('vm/device/virtual');
  assert.equal(initial.isMicEnabled, false, 'Microphone must be idle');
  assert.equal(initial.isNetworkEnabled, true, 'NCM must initially be enabled');
  assert.equal((await api('storage/image/mounted')).file, '', 'Existing media must be ejected first');
  started = true;
  for (let cycle = 0; cycle < 3; cycle++) {
    await api('vm/device/virtual', { device: 'mic' });
    assert.equal((await api('vm/device/virtual')).isMicEnabled, true);
    await api('storage/image/mount', { file: image, cdrom: true, readOnly: true });
    assert.equal((await api('storage/image/mounted')).file, image);
    await api('storage/image/mount', { file: '' });
    assert.equal((await api('vm/device/virtual')).isMicEnabled, true);
    await api('vm/device/virtual', { device: 'mic' });
    const state = await api('vm/device/virtual');
    assert.equal(state.isMicEnabled, false);
    assert.equal(state.isNetworkEnabled, true);
    console.log(`PASS: microphone + media + eject + NCM cycle ${cycle + 1}/3`);
  }
} finally {
  try {
    if (started) {
      await api('storage/image/mount', { file: '' });
      if ((await api('vm/device/virtual')).isMicEnabled) await api('vm/device/virtual', { device: 'mic' });
    }
  } finally {
    await browser.close();
  }
}
