// Exclusive HDMI regression. Uses a configured or explicitly initialized test instance.
// Saves downloaded recordings locally; removes only recordings created by this test.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
const url = process.env.ONEKVM_URL || 'http://192.168.50.210:8080';
const username = process.env.ONEKVM_USERNAME, password = process.env.ONEKVM_PASSWORD;
assert(username && password, 'Set ONEKVM_USERNAME and ONEKVM_PASSWORD');
const output = process.env.RECORDING_OUTPUT || 'logs/one-kvm-recording';
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'en-US' });
let saved, tone;
const created = new Set();
const openRecording = async page => {
  const collapse = page.getByRole('button', { name: 'Collapse toolbar', exact: true });
  if (await collapse.isVisible()) await collapse.click();
  await page.getByRole('button', { name: 'Device recording', exact: true }).click();
};
const api = async (endpoint, method = 'GET', data) => {
  const response = await context.request.fetch(url + '/api/' + endpoint, { method, data });
  assert(response.ok(), `${method} ${endpoint}: ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
};
try {
  const unauthorized = await context.request.get(url + '/api/recording');
  assert.equal(unauthorized.status(), 401);
  if (!(await api('setup')).initialized) {
    assert(process.argv.includes('--initialize'), 'Test instance needs explicit --initialize');
    await api('setup/init', 'POST', { username, password, video_device: '/dev/video_cap',
      audio_device: 'hw:AMLAUGESOUND,0', ttyd_enabled: false, rustdesk_enabled: false, msd_enabled: false });
  }
  await api('auth/login', 'POST', { username, password });
  assert.equal((await api('recording')).recording, false, 'Do not interrupt an existing recording');
  const layouts = process.env.ONEKVM_CONSOLE_LAYOUT ? [process.env.ONEKVM_CONSOLE_LAYOUT] : ['floating', 'sidebar', 'current'];
  const layoutPage = await context.newPage();
  await layoutPage.goto(url + '/api/setup');
  for (const layout of layouts) {
    await layoutPage.evaluate(layout => localStorage.setItem('consoleLayout', layout), layout);
    await layoutPage.goto(url);
    await layoutPage.getByRole('button', { name: 'Device recording', exact: true }).waitFor();
    await openRecording(layoutPage);
    await layoutPage.keyboard.press('Escape');
  }
  await layoutPage.close();
  saved = { mode: await api('stream/mode'), audio: await api('config/audio') };
  await api('config/audio', 'PATCH', { enabled: true });
  for (const codec of ['h264', 'h265']) {
    await api('stream/mode', 'POST', { mode: codec });
    for (let attempt = 0; ; attempt++) {
      const mode = await api('stream/mode');
      if (!mode.switching && mode.mode === codec) break;
      assert(attempt < 30, 'Video mode did not settle');
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (process.env.HDMI_TONE) {
      tone = spawn(process.env.HDMI_TONE, [process.env.HDMI_AUDIO_NAME || 'RTK UHD HDR'], { stdio: 'ignore' });
    }
    let page = await context.newPage();
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, null, { timeout: 30000 });
    await openRecording(page);
    await page.getByRole('button', { name: 'Start recording', exact: true }).click();
    await page.getByRole('button', { name: /Stop and save/ }).waitFor({ timeout: 20000 });
    const running = await api('recording');
    assert.equal(running.recording, true);
    created.add(running.file);
    for (const [endpoint, method] of [['recording/start', 'POST'], [`recording/files/${running.file}`, 'GET'], [`recording/files/${running.file}`, 'DELETE']]) {
      assert.equal((await context.request.fetch(url + '/api/' + endpoint, { method })).status(), 409);
    }
    await page.close();
    // No browser video/audio consumer remains during this interval.
    for (let second = 0; second < 12; second++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const current = await api('recording');
      assert.equal(current.recording, true, JSON.stringify(current));
    }
    page = await context.newPage();
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, null, { timeout: 30000 });
    await openRecording(page);
    await page.getByRole('button', { name: /Stop and save/ }).click();
    await page.getByRole('button', { name: 'Start recording', exact: true }).waitFor({ timeout: 15000 });
    const stopped = await api('recording');
    assert.equal(stopped.error, null, JSON.stringify(stopped));
    assert(stopped.file.endsWith('.mkv'));
    created.delete(running.file); created.add(stopped.file);
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Download', exact: true }).first().click();
    const download = await downloadEvent;
    await download.saveAs(path.join(output, `${codec}.mkv`));
    const files = await api('recording/files');
    const file = files.find(file => file.name === stopped.file);
    assert(file.complete && file.bytes > 100000);
    await page.screenshot({ path: path.join(output, `${codec}-recording.png`) });
    console.log(JSON.stringify({ codec, ...stopped, bytes: file.bytes }));
    // Exercise the actual UI client: successful deletion must not produce a parse-error toast.
    const visibleErrors = [];
    await page.exposeFunction('recordDeletionError', text => visibleErrors.push(text));
    await page.evaluate(() => {
      const observer = new MutationObserver(() => {
        for (const node of document.querySelectorAll('[role="alert"], [data-sonner-toast][data-type="error"]')) {
          window.recordDeletionError(node.textContent);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    });
    const row = page.getByRole('dialog').locator('div.rounded.border').filter({ hasText: stopped.file });
    page.once('dialog', dialog => dialog.accept());
    const deleted = page.waitForResponse(response => response.request().method() === 'DELETE'
      && response.url().endsWith(`/recording/files/${stopped.file}`));
    await row.getByRole('button', { name: 'Delete', exact: true }).click();
    assert((await deleted).ok());
    await row.waitFor({ state: 'detached' });
    assert.deepEqual(visibleErrors, [], 'Successful deletion displayed an error');
    assert(!(await api('recording/files')).some(file => file.name === stopped.file));
    created.delete(stopped.file);
    await page.close();
    tone?.kill(); tone = undefined;
  }
  // Audio shutdown must stop the recording with a visible error, then allow restart.
  const running = await api('recording/start', 'POST'); created.add(running.file);
  await api('audio/stop', 'POST');
  let interrupted;
  for (let second = 0; second < 15; second++) {
    interrupted = await api('recording');
    if (!interrupted.recording) break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  assert(!interrupted.recording && interrupted.error, JSON.stringify(interrupted));
  created.delete(running.file); created.add(interrupted.file);
  console.log(JSON.stringify({ interruption: interrupted }));
  await api('audio/start', 'POST');
  const restarted = await api('recording/start', 'POST'); created.add(restarted.file);
  const stopped = await api('recording/stop', 'POST');
  created.delete(restarted.file); created.add(stopped.file);
  assert.equal(stopped.error, null, JSON.stringify(stopped));
  const beforeSwitch = await api('recording/start', 'POST'); created.add(beforeSwitch.file);
  await api('stream/mode', 'POST', { mode: 'h264' });
  let switched;
  for (let second = 0; second < 15; second++) {
    switched = await api('recording');
    if (!switched.recording) break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  assert(!switched.recording && switched.error, JSON.stringify(switched));
  created.delete(beforeSwitch.file); created.add(switched.file);
  console.log(JSON.stringify({ codecSwitch: switched }));
  console.log('PASS: authenticated recording, duplicate start, file protection, closed-browser recording, download, audio interruption, restart and codec change');
} catch (error) {
  const page = context.pages().at(-1);
  if (page) {
    await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
    await fs.writeFile(path.join(output, 'failure.txt'), await page.locator('body').innerText().catch(() => ''));
  }
  throw error;
} finally {
  tone?.kill();
  if (saved) {
    try {
      const stopped = await api('recording/stop', 'POST');
      if (stopped.file && created.has(stopped.file + '.part')) created.add(stopped.file);
      for (const file of await api('recording/files')) if (created.has(file.name)) await api(`recording/files/${file.name}`, 'DELETE');
      await api('config/audio', 'PATCH', saved.audio);
      await api('stream/mode', 'POST', { mode: saved.mode.mode });
    } catch (error) { console.error('Cleanup failed:', error.message); process.exitCode = 1; }
  }
  await browser.close();
}
