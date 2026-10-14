// macOS host regression: authenticated HID input, read-only ISO mount/eject,
// then HID input again after USB re-enumeration. Run only with exclusive access.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
assert(process.env.ONEKVM_TEST_ISO, 'Set ONEKVM_TEST_ISO to an ISO containing readme.txt with the test marker');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const pointer = () => execFileSync('osascript', ['-l', 'JavaScript', '-e',
  'ObjC.import("AppKit"); const p=$.NSEvent.mouseLocation; const f=$.NSScreen.screens.objectAtIndex(0).frame; [p.x/f.size.width,1-p.y/f.size.height].join(" ")'], { encoding: 'utf8' }).trim().split(' ').map(Number);
const original = pointer();
let imageId;
const api = (path, method = 'GET', body) => page.evaluate(async ({ path, method, body }) => {
  const response = await fetch('/api/' + path, { method,
    headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
  if (!response.ok) throw new Error(path + ' HTTP ' + response.status + ': ' + await response.text());
  return response.json();
}, { path, method, body });
const move = async ([x, y]) => {
  await page.evaluate(([x, y]) => {
    const data = new Uint8Array(7);
    data[0] = 2; data[1] = 1;
    const view = new DataView(data.buffer);
    view.setUint16(2, Math.round(x * 32767), true);
    view.setUint16(4, Math.round(y * 32767), true);
    window.usbSocket.send(data);
  }, [x, y]);
};
const checkPointer = async () => {
  for (const target of [[0.25, 0.25], [0.7, 0.6]]) {
    await move(target);
    await page.waitForTimeout(500);
    const actual = pointer();
    assert(actual.every((value, i) => Math.abs(value - target[i]) < 0.02), `Pointer ${actual}, expected ${target}`);
  }
};
try {
  await page.goto('http://192.168.50.210:8080/api/setup');
  await api('auth/login', 'POST', { username: process.env.ONEKVM_USERNAME, password: process.env.ONEKVM_PASSWORD });
  await page.evaluate(() => new Promise((resolve, reject) => {
    const socket = window.usbSocket = new WebSocket(`ws://${location.host}/api/ws/hid`);
    socket.binaryType = 'arraybuffer';
    socket.onmessage = event => new Uint8Array(event.data)[0] === 0 ? resolve() : reject(new Error('HID unavailable'));
    socket.onerror = reject;
  }));
  await checkPointer();
  await page.evaluate(() => window.usbSocket.send(new Uint8Array([1, 0, 0xe1, 2])));
  await page.waitForTimeout(300);
  const flags = Number(execFileSync('osascript', ['-l', 'JavaScript', '-e', 'ObjC.import("AppKit"); $.NSEvent.modifierFlags'], { encoding: 'utf8' }).trim());
  await page.evaluate(() => window.usbSocket.send(new Uint8Array([1, 1, 0xe1, 0])));
  assert(flags & (1 << 17), 'Host did not receive Shift key');
  const encoded = readFileSync(process.env.ONEKVM_TEST_ISO).toString('base64');
  imageId = await page.evaluate(async encoded => {
    const form = new FormData();
    form.append('file', new Blob([Uint8Array.from(atob(encoded), c => c.charCodeAt(0))]), `vim4-smoke-${Date.now()}.iso`);
    const response = await fetch('/api/msd/images', { method: 'POST', body: form });
    if (!response.ok) throw new Error('Upload HTTP ' + response.status);
    return (await response.json()).id;
  }, encoded);
  await api(`msd/images/${imageId}/mount`, 'POST', { cdrom: true, read_only: true });
  let marker;
  for (let i = 0; i < 30; i++) {
    try { marker = readFileSync('/Volumes/ONEKVM_TEST/readme.txt', 'utf8'); break; } catch {}
    await page.waitForTimeout(500);
  }
  assert.equal(marker?.trim(), 'One-KVM VIM4 virtual media validation', 'Host did not read the ISO');
  await checkPointer();
  await api(`msd/images/${imageId}/mount`, 'DELETE');
  await page.waitForTimeout(1500);
  await checkPointer();
  console.log('PASS: host keyboard, pointer, ISO contents, eject and pointer after re-enumeration');
} finally {
  if (imageId) {
    await api(`msd/images/${imageId}/mount`, 'DELETE').catch(() => {});
    await api(`msd/images/${imageId}`, 'DELETE').catch(error => console.error('Test image cleanup failed:', error.message));
  }
  await page.evaluate(() => window.usbSocket?.send(new Uint8Array([1, 1, 0xe1, 0]))).catch(() => {});
  await move(original).catch(() => {});
  await browser.close();
}
