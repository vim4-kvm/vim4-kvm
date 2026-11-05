// Live manager check inside an approved board ticket. Expects standard thermal
// fan trips and TCPM; VIM4_EXPECTED_RELEASE identifies this window's kernel.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { loginManager } from '../../tools/manager-login.mjs';
const expected = process.env.VIM4_EXPECTED_RELEASE;
assert(expected, 'Set VIM4_EXPECTED_RELEASE to the candidate release');
assert(process.env.BOARD_TICKET, 'Run inside the approved board-queue window');
const logs = process.env.VIM4_FINAL_LOGS;
assert(logs, 'Set VIM4_FINAL_LOGS to this window log directory');
await mkdir(logs, { recursive: true });
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
const url = process.env.MANAGER_URL || 'http://192.168.50.210';
try {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  await context.addInitScript(() => localStorage.setItem('vim4-manager-language', 'zh-CN'));
  await loginManager(context, url);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await context.request.get(url + '/api/kernel');
  assert(response.ok());
  const kernels = await response.json();
  assert.equal(kernels.running, expected);
  assert(kernels.kernels.some(k => k.id === 'mainline' && k.release === expected && k.available && k.selected));
  assert(kernels.kernels.some(k => k.id === 'vendor' && k.available));
  await page.goto(url + '/#/updates');
  await page.getByText(expected, { exact: true }).waitFor();
  await page.getByText('当前运行', { exact: true }).waitFor();
  await page.screenshot({ path: logs + '/manager-kernel.png', fullPage: true });
  await page.goto(url + '/#/overview');
  await page.getByRole('tab', { name: '功耗', exact: true }).click();
  await page.getByText('PD 协商', { exact: true }).waitFor();
  const statusResponse = await context.request.get(url + '/api/status');
  assert(statusResponse.ok());
  const status = await statusResponse.json();
  assert.equal(status.hardware.kernel, expected);
  assert.equal(status.hardware.usb, 'configured');
  assert(status.power?.firmwarePD, 'The PD firmware card must receive its handoff snapshot');
  assert.deepEqual(status.power.kernelPD, { state: 'ready', contract: { voltageV: 5, currentA: 3 } });
  await page.getByText('5 V / 3 A', { exact: true }).waitFor();
  await page.screenshot({ path: logs + '/manager-pd.png', fullPage: true });
  assert.equal(status.hardware.fanAuto, true);
  assert.equal(status.hardware.fanCurve?.length, 15);
  assert(status.hardware.fanTriggers, 'Standard thermal fan anchors must be editable');
  const curve = status.hardware.fanCurve;
  assert.deepEqual(curve.map(p => p.percent), [5, 10, 15, 20, 25, 30, 35, 43, 52, 61, 70, 77, 85, 92, 100]);
  assert(curve.every((p, i) => Number.isFinite(p.tempC) && (!i || p.tempC > curve[i - 1].tempC)));
  assert.deepEqual([curve[6].tempC, curve[10].tempC, curve[14].tempC],
    ['low', 'mid', 'high'].map(key => status.hardware.fanTriggers[key]));
  await page.goto(url + '/#/cooling');
  await page.getByRole('button', { name: '应用曲线', exact: true }).waitFor();
  await page.screenshot({ path: logs + '/manager-cooling.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: logs + '/manager-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ running: kernels.running, power: status.power,
    fanTriggers: status.hardware.fanTriggers, fanCurve: curve, mobileOverflow: false }));
} finally {
  await browser.close();
}
