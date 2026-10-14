// Real Ventoy creation and file round-trip against an exclusively reserved board.
// --initialize creates a missing 256 MiB drive; an existing drive is never reformatted.
// --mount-host additionally verifies the uploaded file through the macOS USB volume.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
assert(process.env.ONEKVM_USERNAME && process.env.ONEKVM_PASSWORD, 'Set One-KVM credentials');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const filename = `vim4-drive-check-${Date.now()}.txt`;
const marker = `One-KVM Ventoy round-trip ${filename}\n`;
let uploaded = false;
let mounted = false;
const api = (path, method = 'GET', body) => page.evaluate(async ({ path, method, body }) => {
  const response = await fetch('/api/' + path, { method,
    headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
  if (!response.ok) throw new Error(path + ' HTTP ' + response.status + ': ' + await response.text());
  return response.json();
}, { path, method, body });
try {
  await page.goto((process.env.ONEKVM_URL || 'http://192.168.50.210:8080') + '/api/setup');
  await api('auth/login', 'POST', { username: process.env.ONEKVM_USERNAME, password: process.env.ONEKVM_PASSWORD });
  const status = await api('msd/status');
  assert.equal(status.available, true, 'Virtual media is unavailable');
  assert.equal(status.state.mounted_count, 0, 'Detach existing virtual media before testing');
  assert.equal(status.state.usb_reenumerating, false);
  let info;
  try {
    info = await api('msd/drive');
  } catch (error) {
    if (!error.message.includes('MSD_DRIVE_NOT_INITIALIZED')) throw error;
  }
  if (!info) {
    assert(process.argv.includes('--initialize'), 'No drive; pass --initialize to create one');
    info = await api('msd/drive/init', 'POST', { size_mb: 256 });
    assert.equal(info.size, 256 * 1024 * 1024);
  }
  assert.equal(info.file_access, 'available');
  await page.evaluate(async ({ filename, marker }) => {
    const form = new FormData();
    form.append('file', new Blob([marker]), filename);
    const response = await fetch('/api/msd/drive/files', { method: 'POST', body: form });
    if (!response.ok) throw new Error('Upload HTTP ' + response.status + ': ' + await response.text());
  }, { filename, marker });
  uploaded = true;
  assert((await api('msd/drive/files')).some(file => file.name === filename));
  const download = await page.evaluate(async filename => {
    const response = await fetch('/api/msd/drive/files/' + filename);
    if (!response.ok) throw new Error('Download HTTP ' + response.status);
    return response.text();
  }, filename);
  assert.equal(download, marker);
  if (process.argv.includes('--mount-host')) {
    await api('msd/drive/mount', 'POST');
    mounted = true;
    let hostContent;
    for (let attempt = 0; attempt < 40; attempt++) {
      try { hostContent = readFileSync('/Volumes/ONE-KVM/' + filename, 'utf8'); break; } catch {}
      await page.waitForTimeout(500);
    }
    assert.equal(hostContent, marker, 'USB host did not read the virtual drive');
    // Flush host filesystem writes before disconnecting the backing image.
    execFileSync('diskutil', ['eject', '/Volumes/ONE-KVM'], { stdio: 'pipe' });
    await api('msd/drive/mount', 'DELETE');
    mounted = false;
  }
  await api('msd/drive/files/' + filename, 'DELETE');
  uploaded = false;
  assert(!(await api('msd/drive/files')).some(file => file.name === filename));
  console.log('PASS: initialized drive, upload/list/download/delete' +
    (process.argv.includes('--mount-host') ? ', USB host contents and eject' : ''));
} finally {
  try {
    if (mounted) {
      execFileSync('diskutil', ['eject', '/Volumes/ONE-KVM'], { stdio: 'pipe' });
      await api('msd/drive/mount', 'DELETE');
    }
    if (uploaded) await api('msd/drive/files/' + filename, 'DELETE');
  } finally {
    await browser.close();
  }
}
