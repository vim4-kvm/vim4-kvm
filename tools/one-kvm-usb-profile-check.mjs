// Exclusive One-KVM USB regression. Requires detached media and restores settings.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access first');
const ssh = command => execFileSync('ssh', ['vim4', command], { encoding: 'utf8' }).trim();
assert.equal(ssh('sudo -n cat /sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file'), '', 'Detach media first');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
const api = (path, method = 'GET', body) => page.evaluate(async ({ path, method, body }) => {
  const response = await fetch('/api/' + path, { method, headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const result = await response.json();
  if (!response.ok) throw new Error(path + ': ' + response.status + ' ' + JSON.stringify(result));
  return result;
}, { path, method, body });
let saved;
try {
  await page.goto(url + '/api/setup');
  await api('auth/login', 'POST', { username: process.env.ONEKVM_USERNAME, password: process.env.ONEKVM_PASSWORD });
  saved = { hid: await api('config/hid'), msd: await api('config/msd'),
    network: await api('config/otg-network'), uac: await api('config/uac') };
  const base = { hid: { ...saved.hid, otg_profile: 'custom', mouse_macos_drag: false,
    otg_functions: { keyboard: true, mouse_absolute: true, mouse_relative: true, consumer: false } },
    msd: { ...saved.msd, enabled: false }, network: { ...saved.network, enabled: false, bridge_interface: '' },
    uac: { enabled: false, sample_rate: 48000, channels: 2 } };
  await api('config/otg', 'PATCH', base);
  for (const functions of [
    { keyboard: true, mouse_absolute: true, mouse_relative: true, consumer: true },
    { keyboard: false, mouse_absolute: true, mouse_relative: false, consumer: false },
    { keyboard: true, mouse_absolute: false, mouse_relative: false, consumer: false },
  ]) {
    await api('config/otg', 'PATCH', { ...base, hid: { ...base.hid, otg_functions: functions, otg_keyboard_leds: true } });
    let status;
    for (let attempt = 0; attempt < 50; attempt++) {
      status = await api('hid/status');
      if (status.online && status.available) break;
      await page.waitForTimeout(100);
    }
    assert(status.online && status.available, JSON.stringify(status));
    assert.equal(status.supports_absolute_mouse, functions.mouse_absolute);
    assert.equal(status.keyboard_leds_enabled, functions.keyboard);
    console.log(JSON.stringify({ functions, status }));
  }
  await api('config/hid', 'PATCH', { backend: 'none' });
  assert.equal((await api('hid/status')).available, false);
  await api('config/otg', 'PATCH', base);
  await api('config/otg', 'PATCH', { ...base, uac: { ...base.uac, enabled: true } });
  assert(ssh('cat /proc/asound/cards').includes('UAC2Gadget'));
  if (process.argv.includes('--audio')) {
    // Existing host diagnostic records the selected USB input; synthetic PCM
    // traverses the same authenticated WebSocket used by the browser microphone.
    const recording = spawn('/tmp/uac-record-level', ['5']);
    let output = '', error = '';
    recording.stdout.on('data', chunk => { output += chunk; });
    recording.stderr.on('data', chunk => { error += chunk; });
    const recorded = new Promise((resolve, reject) => {
      recording.on('error', reject);
      recording.on('close', code => code === 0 ? resolve(output) : reject(new Error(error)));
    });
    await page.evaluate(() => new Promise((resolve, reject) => {
      const socket = new WebSocket(`ws://${location.host}/api/ws/uac-audio`);
      let frame = 0, timer;
      socket.onopen = () => {
        timer = setInterval(() => {
          const packet = new Uint8Array(15 + 960 * 4), view = new DataView(packet.buffer);
          packet[0] = 4;
          view.setUint32(11, 960 * 4, true);
          for (let i = 0; i < 960; i++) {
            const sample = Math.round(5000 * Math.sin(2 * Math.PI * 440 * (frame * 960 + i) / 48000));
            view.setInt16(15 + i * 4, sample, true);
            view.setInt16(17 + i * 4, sample, true);
          }
          socket.send(packet);
          if (++frame === 300) { clearInterval(timer); socket.close(); resolve(true); }
        }, 20);
      };
      socket.onerror = () => { clearInterval(timer); reject(new Error('Microphone socket failed')); };
    }));
    const level = JSON.parse(await recorded);
    console.log(JSON.stringify({ microphone: level }));
    assert(level.device.includes('One-KVM') || level.device.includes('vim4'), 'Host default input is not the USB microphone');
    assert(level.rms > 0.02 && level.frequency > 400 && level.frequency < 480, 'USB microphone did not deliver the tone');
  }
  for (const driver_mode of ['ncm', 'ecm', 'rndis']) {
    await api('config/otg', 'PATCH', { ...base, network: { ...base.network, enabled: true, driver_mode } });
    console.log('PASS: network ' + driver_mode);
  }
  await assert.rejects(api('config/otg', 'PATCH', {
    hid: { otg_functions: { ...base.hid.otg_functions, consumer: true } },
  }), /endpoint/);
  assert.equal((await api('config/hid')).otg_functions.consumer, false);
  await api('config/otg', 'PATCH', base);
  await page.goto(url + '/settings');
  await page.getByRole('button', { name: 'HID', exact: true }).click();
  await page.locator('#otg-product').fill('One-KVM USB UI Test');
  const response = page.waitForResponse(r => r.url().endsWith('/api/config/otg') && r.request().method() === 'PATCH');
  await page.getByRole('button', { name: /保存功能配置|Save.*[Ff]eature/ }).click();
  assert((await response).ok());
  assert.equal(ssh('cat /sys/kernel/config/usb_gadget/kvm/strings/0x409/product'), 'One-KVM USB UI Test');
  await page.screenshot({ path: 'logs/one-kvm/usb-settings.png', fullPage: true });
  console.log('PASS: HID settings rendered and saved through the UI');
} finally {
  try {
    if (saved) await api('config/otg', 'PATCH', saved);
  } finally { await browser.close(); }
}
