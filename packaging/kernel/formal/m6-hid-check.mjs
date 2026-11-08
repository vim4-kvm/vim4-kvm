// Browser transport runs on M4; only M6's disposable native window receives HID.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { loginManager } from '../../../tools/manager-login.mjs';
assert(process.env.BOARD_TICKET, 'Requires the approved board ticket');
assert(process.env.M6_SSH_HOST && process.env.M6_FIXTURE_DIR, 'Requires a verified M6 SSH route');
const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
const target = spawn('ssh', ['-oBatchMode=yes', '-oConnectTimeout=5', process.env.M6_SSH_HOST,
  'python3 ' + quote(process.env.M6_FIXTURE_DIR + '/host.py') + ' hid']);
target.stderr.pipe(process.stderr);
const events = [];
let exited = false;
target.on('exit', () => { exited = true; });
target.on('error', error => { console.error(error); exited = true; });
createInterface({ input: target.stdout }).on('line', row => { const event = JSON.parse(row); events.push(event); console.log(row); });
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
let page;
async function until(check, label) {
  const deadline = Date.now() + 10000;
  while (!check()) {
    assert(!exited, 'M6 input target exited: ' + label);
    assert(Date.now() < deadline, 'M6 did not receive ' + label);
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}
async function send(data) {
  await page.evaluate(data => window.usbSocket.send(new Uint8Array(data)), data);
}
try {
  await until(() => events.some(e => e.kind === 'ready'), 'native target readiness');
  const context = await browser.newContext();
  const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
  await loginManager(context, url);
  page = await context.newPage();
  await page.goto(url + '/api/setup');
  await page.evaluate(() => new Promise((resolve, reject) => {
    const socket = window.usbSocket = new WebSocket(`ws://${location.host}/api/ws/hid`);
    socket.binaryType = 'arraybuffer';
    socket.onmessage = event => new Uint8Array(event.data)[0] === 0 ? resolve() : reject(new Error('HID unavailable'));
    socket.onerror = reject;
  }));
  await send([1, 0, 0x4f, 0]);
  await until(() => events.some(e => e.kind === 'keydown' && e.key === 124), 'arrow key down');
  await send([1, 1, 0x4f, 0]);
  await until(() => events.some(e => e.kind === 'keyup' && e.key === 124), 'arrow key up');
  for (const [x, y] of [[8192, 8192], [22937, 19660]]) {
    const beforeAbsolute = events.filter(e => e.kind === 'move').length;
    const packet = new Uint8Array(7); packet[0] = 2; packet[1] = 1;
    const view = new DataView(packet.buffer); view.setUint16(2, x, true); view.setUint16(4, y, true);
    await send([...packet]);
    await until(() => events.filter(e => e.kind === 'move').length > beforeAbsolute, 'absolute pointer movement');
  }
  const last = events.filter(e => e.kind === 'move').at(-1);
  await send([2, 0, 24, 0, 16, 0, 0]);
  await until(() => events.some(e => e.kind === 'move' && e.receivedMs > last.receivedMs && e.x > last.x && e.y > last.y), 'relative pointer movement');
  await send([2, 2, 0, 0, 0, 0, 0]);
  await until(() => events.some(e => e.kind === 'mousedown'), 'mouse down');
  await send([2, 3, 0, 0, 0, 0, 0]);
  await until(() => events.some(e => e.kind === 'mouseup'), 'mouse up');
  await send([2, 4, 0, 0, 0, 0, 1]);
  await until(() => events.some(e => e.kind === 'wheel' && e.dy !== 0), 'wheel movement');
  console.log(JSON.stringify({ passed: true, receiver: 'M6 native input-target', events }));
} finally {
  try {
    if (page) {
      await send([1, 1, 0x4f, 0]);
      await send([2, 3, 0, 0, 0, 0, 0]);
    }
  } finally {
    target.stdin.end();
    await browser.close();
  }
}

