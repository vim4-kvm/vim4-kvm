import { loginManager } from './manager-login.mjs';
// Exclusive One-KVM USB regression. Requires detached media and restores settings.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access first');
const ssh = command => execFileSync('ssh', ['vim4', command], { encoding: 'utf8' }).trim();
assert.equal(ssh('sudo -n cat /sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file'), '', 'Detach media first');
assert.equal(ssh('cat /proc/sys/kernel/tainted'), '0', 'Requires an untainted kernel baseline');
const kernelStart = ssh('date +%s');
const browser = await chromium.launch({
  ...(process.env.VIM4_TEST_CHROME ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }),
  headless: !process.argv.includes('--headed'),
  args: ['--autoplay-policy=no-user-gesture-required'],
});
const prefix = process.argv.find(x => x.startsWith('--output-prefix='))?.split('=')[1] || 'logs/one-kvm/usb';
const page = await browser.newPage();
page.on('console', message => {
  if (message.text().startsWith('USB microphone:')) console.log(message.text());
});
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
  await loginManager(page.context(), url);
  await page.goto(url + '/api/setup');
  saved = { hid: await api('config/hid'), msd: await api('config/msd'),
    network: await api('config/otg-network'), uac: await api('config/uac') };
  assert.equal(saved.hid.backend, 'otg', 'Enable OTG before this hardware regression');
  writeFileSync(prefix + '-original-config.json', JSON.stringify(saved, null, 2), { flag: 'wx' });
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
  if (process.argv.includes('--audio') || process.argv.includes('--browser-audio')) {
    // Existing host diagnostic records the selected USB input; synthetic PCM
    // traverses the same authenticated WebSocket used by the browser microphone.
    await page.waitForTimeout(1500); // allow the host audio device to enumerate
    // Keep PCM running while the host opens its input. Some host drivers wait
    // for the first USB samples before resolving getUserMedia.
    await page.evaluate(() => new Promise((resolve, reject) => {
      const socket = new WebSocket(`ws://${location.host}/api/ws/uac-audio`);
      let frame = 0, timer, watchdog;
      window.usbToneStop = () => { clearInterval(timer); clearTimeout(watchdog); socket.close(); };
      socket.onopen = () => {
        timer = setInterval(() => {
          const packet = new Uint8Array(15 + 960 * 4), view = new DataView(packet.buffer);
          packet[0] = 4; view.setUint32(11, 960 * 4, true);
          for (let i = 0; i < 960; i++) {
            const sample = Math.round(5000 * Math.sin(2 * Math.PI * 440 * (frame * 960 + i) / 48000));
            view.setInt16(15 + i * 4, sample, true);
            view.setInt16(17 + i * 4, sample, true);
          }
          socket.send(packet); frame++;
        }, 20);
        watchdog = setTimeout(window.usbToneStop, 60000);
        resolve();
      };
      socket.onerror = () => { window.usbToneStop(); reject(new Error('Microphone socket failed')); };
    }));
    let recorded;
    if (process.argv.includes('--browser-audio')) {
      await page.context().grantPermissions(['microphone'], { origin: url });
      recorded = page.evaluate(async () => {
        const inputs = (await navigator.mediaDevices.enumerateDevices()).filter(device =>
          device.kind === 'audioinput' && !['default', 'communications'].includes(device.deviceId) &&
          /One-KVM|UAC2|Capture Inactive/i.test(device.label));
        if (inputs.length !== 1) throw new Error('Expected one identified USB microphone: ' +
          JSON.stringify(inputs.map(d => d.label)));
        console.log('USB microphone: opening ' + inputs[0].label);
        const stream = await navigator.mediaDevices.getUserMedia({ video: false, audio: {
          deviceId: { exact: inputs[0].deviceId }, echoCancellation: false,
          noiseSuppression: false, autoGainControl: false } });
        console.log('USB microphone: capture stream ready');
        const audio = new AudioContext();
        try {
          await audio.resume();
          console.log('USB microphone: audio context ' + audio.state);
          const source = audio.createMediaStreamSource(stream), analyser = audio.createAnalyser();
          analyser.fftSize = 4096; source.connect(analyser);
          const wave = new Float32Array(analyser.fftSize), spectrum = new Float32Array(analyser.frequencyBinCount);
          let rms = 0, frequency = 0;
          const end = performance.now() + 5000;
          while (performance.now() < end) {
            analyser.getFloatTimeDomainData(wave);
            const level = Math.sqrt(wave.reduce((sum, v) => sum + v * v, 0) / wave.length);
            if (level > rms) {
              rms = level; analyser.getFloatFrequencyData(spectrum);
              let maximum = 0;
              for (let bin = 1; bin < spectrum.length; bin++) if (spectrum[bin] > spectrum[maximum]) maximum = bin;
              frequency = maximum * audio.sampleRate / analyser.fftSize;
            }
            await new Promise(resolve => setTimeout(resolve, 10));
          }
          return JSON.stringify({ device: inputs[0].label, rms, frequency, capture: 'browser-exact-usb-device' });
        } finally { stream.getTracks().forEach(track => track.stop()); await audio.close(); }
      });
    } else {
      const recording = spawn('/tmp/uac-record-level', ['5', base.hid.otg_descriptor.manufacturer]);
      let output = '', error = '';
      recording.stdout.on('data', chunk => { output += chunk; });
      recording.stderr.on('data', chunk => { error += chunk; });
      recorded = new Promise((resolve, reject) => {
        recording.on('error', reject);
        recording.on('close', code => code === 0 ? resolve(output) : reject(new Error(error)));
      });
    }
    let timeout;
    const deadline = new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('USB microphone capture timed out')),
      process.argv.includes('--headed') ? 55000 : 20000); });
    let level;
    try { level = JSON.parse(await Promise.race([recorded, deadline])); }
    finally { clearTimeout(timeout); await page.evaluate(() => window.usbToneStop()); }
    console.log(JSON.stringify({ microphone: level }));
    if (!process.argv.includes('--browser-audio')) assert.equal(level.manufacturer, base.hid.otg_descriptor.manufacturer);
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
  await page.screenshot({ path: prefix + '-settings.png', fullPage: true });
  console.log('PASS: HID settings rendered and saved through the UI');
} finally {
  try {
    await page.evaluate(() => window.usbToneStop?.()).catch(() => {});
    if (saved) await api('config/otg', 'PATCH', saved);
  } finally { await browser.close(); }
}
const kernel = ssh(`sudo -n journalctl -k --since=@${kernelStart} --no-pager`);
assert(!/WARNING:|BUG:|Oops:|trying to register non-static key/.test(kernel),
  'USB profile transitions produced a kernel warning; inspect the kernel journal');
assert.equal(ssh('cat /proc/sys/kernel/tainted'), '0');
console.log('PASS: USB transitions and restore produced no kernel warnings');
