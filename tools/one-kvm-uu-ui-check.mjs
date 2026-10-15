// Run against a disposable, uninitialized One-KVM instance, never the board account.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.ONEKVM_URL || 'http://127.0.0.1:18089';
assert.equal(new URL(url).hostname, '127.0.0.1');
const container = process.env.ONEKVM_TEST_CONTAINER;
assert(container?.startsWith('vim4-uu-ui-test-'));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext();
const credentials = { username: 'fixture-admin', password: 'fixture-only-password' };
const api = async (path, method = 'GET', data) => {
  const response = await context.request.fetch(url + '/api/' + path, { method, data });
  assert(response.ok(), `${path}: ${response.status()}`);
  return response.json();
};
try {
  assert.equal((await api('setup')).needs_setup, true, 'Refusing to change an existing installation');
  await api('setup/init', 'POST', credentials);
  await api('auth/login', 'POST', credentials);
  const initial = await api('config/uu-remote');
  assert.equal(initial.config.device_name, 'vim4-kvm');
  assert.equal(initial.config.system, 'windows');
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url + '/settings?tab=third-party-access');
  const name = page.locator('#uu-device-name');
  await name.waitFor({ state: 'visible' });
  assert.equal(await name.inputValue(), 'vim4-kvm');
  await name.fill('Fixture Mac');
  const form = name.locator('..');
  await form.getByRole('combobox').click();
  await page.getByRole('option', { name: 'Mac / macOS', exact: true }).click();
  const saved = page.waitForResponse(r => r.url().endsWith('/api/config/uu-remote') && r.request().method() === 'PATCH');
  await form.getByRole('button').click();
  assert.equal((await saved).status(), 200);
  assert.deepEqual((await api('config/uu-remote')).config, { enabled: false, system: 'macos', device_name: 'Fixture Mac' });
  assert.equal(await page.locator('[data-testid="vim4-video-settings"]:visible').count(), 1);
  assert.equal(await page.locator('[data-testid="vim4-video-settings"]:visible input[type="number"]').count(), 1);
  for (const invalid of [{ device_name: '  ' }, { device_name: 'a\nb' }, { device_name: 'x'.repeat(65) }, { system: 'linux' }]) {
    const response = await context.request.patch(url + '/api/config/uu-remote', { data: invalid });
    assert(response.status() >= 400 && response.status() < 500);
    assert.equal((await api('config/uu-remote')).config.device_name, 'Fixture Mac');
  }
  execFileSync('docker', ['restart', container], { stdio: 'pipe' });
  await page.waitForFunction(async () => { try { return (await fetch('/api/setup')).ok; } catch { return false; } }, null, { timeout: 15000 });
  await api('auth/login', 'POST', credentials);
  assert.equal((await api('config/uu-remote')).config.system, 'macos');
  const restored = await api('config/uu-remote', 'PATCH', { system: 'windows', device_name: ' vim4-kvm ' });
  assert.equal(restored.config.device_name, 'vim4-kvm');
  assert.equal(restored.config.system, 'windows');
  assert.equal(restored.status.logged_in, false);
  assert.deepEqual(errors, []);
  console.log('PASS: browser profile save, output controls, validation, restart persistence, system switch');
} finally {
  await browser.close();
}
