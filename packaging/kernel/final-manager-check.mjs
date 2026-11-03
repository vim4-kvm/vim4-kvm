// Live board check, called only from the board/heavy locked final window.
import assert from 'node:assert/strict';
import { loginManager } from '../../tools/manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
const url = 'http://192.168.50.210';
try {
  const context = await browser.newContext();
  await loginManager(context, url);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await context.request.get(url + '/api/kernel');
  assert(response.ok());
  const kernels = await response.json();
  assert.equal(kernels.running, '7.3.0-vim4kvm-uhd1+');
  assert(kernels.kernels.some(k => k.release === kernels.running && k.available && k.selected));
  await page.goto(url + '/#/updates');
  await page.locator('.kernel-panel').getByText('正式版', { exact: true }).waitFor();
  await page.locator('.kernel-panel').getByText('正在运行', { exact: true }).waitFor();
  await page.screenshot({ path: process.env.VIM4_FINAL_LOGS + '/manager-kernel.png', fullPage: true });
  await page.goto(url + '/#/overview');
  await page.getByText('PD 协商', { exact: true }).waitFor();
  const status = await (await context.request.get(url + '/api/status')).json();
  assert(status.power?.firmwarePD, 'The PD firmware card must receive its handoff snapshot');
  await page.screenshot({ path: process.env.VIM4_FINAL_LOGS + '/manager-pd.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: process.env.VIM4_FINAL_LOGS + '/manager-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ running: kernels.running, power: status.power, mobileOverflow: false }));
} finally {
  await browser.close();
}
