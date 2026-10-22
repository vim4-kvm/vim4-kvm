// macOS host acceptance of a dedicated FAT image, read-only and writable.
// Requires an unused EDGEUSB21 image containing marker.txt; never use user media.
// Restores USB settings only after host eject and an empty kernel LUN.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { loginManager } from './manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
assert(args.includes('--exclusive'), 'Requires exclusive board and USB host access');
const image = args.find(x => x.startsWith('--image='))?.slice(8);
const service = args.find(x => x.startsWith('--service='))?.split('=')[1] || 'one-kvm-edge';
assert(['one-kvm','one-kvm-edge'].includes(service),'Choose the installed One-KVM service');
const managerURL = args.find(x => x.startsWith('--manager-url='))?.slice('--manager-url='.length);
assert(image?.endsWith('.img'), '--image requires a dedicated raw FAT .img fixture');
const volume = '/Volumes/EDGEUSB21';
assert(!existsSync(volume), 'The dedicated test volume must be absent initially');
const marker = 'VIM4 edge USB transfer validation';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
const ssh = (...words) => execFileSync('ssh', ['vim4', words.map(quote).join(' ')],
  { timeout: 25000, maxBuffer: 8 * 1024 * 1024 });
const lun = () => ssh('sudo', '-n', 'cat', '/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file').toString().trim();
assert.equal(lun(), '', 'Safely eject and detach existing media before this test');
const browser = await chromium.launch({ headless: true,
  ...(process.env.VIM4_TEST_CHROME ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }) });
const context = await browser.newContext();
const page = await context.newPage();
const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
let saved, imageId, backing, hostMounted = false, originalError;
const api = async (path, method = 'GET', data) => {
  const response = await context.request.fetch(url + '/api/' + path, { method, ...(data === undefined ? {} : { data }) });
  assert(response.ok(), `${path}: ${response.status()} ${await response.text()}`);
  return response.json();
};
async function until(check, description, timeout = 20000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await check()) return; await page.waitForTimeout(250); }
  throw new Error('Timeout: ' + description);
}
function diskInfo() {
  return JSON.parse(execFileSync('plutil', ['-convert', 'json', '-o', '-', '-'],
    { input: execFileSync('diskutil', ['info', '-plist', volume]) }));
}
async function eject() {
  if (!existsSync(volume) && lun() === '') hostMounted = false;
  if (hostMounted || existsSync(volume + '/marker.txt')) {
    const info = diskInfo();
    assert.equal(info.BusProtocol, 'USB');
    assert.equal(readFileSync(volume + '/marker.txt', 'utf8').trim(), marker);
    execFileSync('diskutil', ['eject', info.ParentWholeDisk], { timeout: 20000 });
    hostMounted = false;
  }
  await until(() => lun() === '', 'host SCSI eject must clear the kernel LUN');
}
try {
  await loginManager(context, url);
  saved = await api('config/otg');
  assert.equal(saved.hid.backend, 'otg');
  const base = { hid: { ...saved.hid, otg_profile: 'full_no_consumer' },
    msd: { ...saved.msd, enabled: false }, network: { ...saved.network, enabled: false, bridge_interface: '' },
    uac: { ...saved.uac, enabled: false }, serial: { ...saved.serial, enabled: false } };
  await api('config/otg', 'PATCH', { ...base, msd: { ...base.msd, enabled: true } });
  const uploaded = await context.request.post(url + '/api/msd/images', {
    multipart: { file: { name: `edge-usb-${Date.now()}.img`, mimeType: 'application/octet-stream', buffer: readFileSync(image) } } });
  assert(uploaded.ok(), await uploaded.text());
  imageId = (await uploaded.json()).id;
  assert(imageId);
  const written = Buffer.alloc(1024 * 1024);
  for (let i = 0; i < written.length; i++) written[i] = (i * 17 + 31) & 255;
  for (const readonly of [true, false]) {
    // The writable trial also exercises all five IN endpoints: three HID,
    // mass storage and UAC2. Audio waveform acceptance is a separate check.
    if (!readonly) await api('config/otg', 'PATCH', { uac: { ...base.uac, enabled: true } });
    await api(`msd/images/${imageId}/mount`, 'POST', { cdrom: false, read_only: readonly });
    backing = lun();
    assert(backing.endsWith('.img'));
    await until(() => existsSync(volume + '/marker.txt'), 'test USB volume mount');
    hostMounted = true;
    const info = diskInfo();
    assert.equal(info.BusProtocol, 'USB');
    assert.equal(info.WritableMedia, !readonly);
    assert.equal(readFileSync(volume + '/marker.txt', 'utf8').trim(), marker);
    if (!readonly) {
      writeFileSync(volume + '/written.bin', written, { flag: 'wx' });
      assert.equal(digest(readFileSync(volume + '/written.bin')), digest(written));
      const device = info.ParentWholeDisk;
      ssh('sudo', '-n', 'systemctl', 'restart', service);
      await until(async () => {
        try { return (await context.request.get(url + '/api/setup')).ok(); }
        catch { return false; }
      }, 'application restart');
      assert.equal(lun(), backing, 'Application restart discarded host-owned media');
      assert.equal(diskInfo().ParentWholeDisk, device, 'Application restart replaced the USB disk');
      assert.equal(digest(readFileSync(volume + '/written.bin')), digest(written));
      const refused = await context.request.patch(url + '/api/config/otg', { data: {
        hid: { otg_descriptor: { ...base.hid.otg_descriptor, product: 'Refused while media is mounted' } } } });
      assert.equal(refused.status(), 400, 'Mounted media must block USB reconfiguration');
      assert.equal(lun(), backing, 'Refused configuration changed the active LUN');
      if (managerURL) {
        const before = await (await context.request.get(managerURL + '/api/kernel')).json();
        for (const [path,data] of [['/api/kernel',{id:'vendor',reboot:false}],['/api/select',{app:'jetkvm'}]]) {
          const rejected = await context.request.post(managerURL + path,{data,headers:{Origin:managerURL}});
          assert.equal(rejected.status(),400,`Mounted media must block ${path}`);
        }
        const after = await (await context.request.get(managerURL + '/api/kernel')).json();
        assert.deepEqual(after,before,'Rejected kernel selection changed the default');
        assert.equal(lun(),backing);
      }
    }
    await eject();
    await api('msd/status');
    // Host eject may already have reconciled application state.
    await page.waitForTimeout(2200);
    if (!readonly) {
      const actual = ssh('mtype', '-i', backing, '::written.bin');
      assert.equal(digest(actual), digest(written));
      ssh('fsck.vfat', '-n', backing);
    }
    console.log(JSON.stringify({ kind: 'media', readonly, hostUsb: true,
      uacEnabled: !readonly,
      applicationRestartPreservedMedia: !readonly,
      writtenBytes: readonly ? 0 : written.length, writtenSha256: readonly ? null : digest(written), hostEjectClearedLun: true }));
  }
  await api(`msd/images/${imageId}`, 'DELETE'); imageId = null;
} catch (error) {
  originalError = error; throw error;
} finally {
  try {
    await eject();
    await api('msd/status');
    if (imageId) await api(`msd/images/${imageId}`, 'DELETE');
    if (saved) await api('config/otg', 'PATCH', { hid: saved.hid, msd: saved.msd,
      network: saved.network, uac: saved.uac, serial: saved.serial });
  } catch (error) {
    if (!originalError) throw error;
    console.error('Cleanup also failed:', error.message);
  } finally { await browser.close(); }
}
console.log(JSON.stringify({ kind: 'complete', restored: true }));
