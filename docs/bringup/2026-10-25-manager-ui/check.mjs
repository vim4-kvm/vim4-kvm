import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { loginManager } from '../../../tools/manager-login.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const base = 'http://192.168.50.210';
const out = process.argv[2];
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const errors = [], reads = [], captures = [];
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('response', response => { if (response.status() >= 400) console.log('HTTP failure', response.status(), new URL(response.url()).pathname); });
  page.on('request', request => {
    if (request.url().startsWith(base) && !['GET', 'HEAD'].includes(request.method())) {
      assert(request.url().endsWith('/__vim4/api/auth/login'), `unexpected write: ${request.method()} ${request.url()}`);
    }
  });
  await page.goto(base + '/__vim4/login');
  await page.getByRole('button', { name: '登录', exact: true }).waitFor();
  await page.screenshot({ path: out + '/login-light-1280.png', fullPage: true });
  captures.push('login-light-1280.png');
  await loginManager(context, base);
  const routes = [
    ['overview', '概览', '/api/status'], ['apps', 'KVM 界面', '/api/status'],
    ['media', '虚拟介质', '/api/media'], ['disks', '数据盘', '/api/disks'],
    ['storage', '网络存储', '/api/storage'], ['video', '视频输入', '/api/edid'],
    ['output', 'HDMI 输出', '/api/passthrough'], ['cooling', '散热', '/api/status'],
    ['network', '网络', '/api/wifi'], ['services', '底层服务', '/api/status'],
    ['updates', '更新', '/api/updates'], ['account', '账户', '/api/account/sessions'],
  ];
  for (const [id, title, endpoint] of routes) {
    const response = page.waitForResponse(r => new URL(r.url()).pathname === endpoint && r.request().method() === 'GET', { timeout: 60000 });
    await page.goto(base + '/#/' + id);
    const result = await response;
    assert(result.ok(), `${title}: HTTP ${result.status()}`);
    reads.push({ page: id, status: result.status() });
    await page.getByRole('heading', { name: title, exact: true, level: 1 }).waitFor();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => !document.querySelector('[data-slot="skeleton"]'), { timeout: 30000 });
    if (id === 'output') {
      const state = await result.json();
      const labels = { running: '透传中', off: '已关闭', 'no-signal': '等待输入信号', 'no-monitor': '未连接显示器', protected: '输入受版权保护', 'unsupported-format': '暂不支持此输入格式', 'video-error': '输入信号异常', unsupported: '当前内核不支持', starting: '正在开启…', stopping: '正在关闭…' };
      await page.getByRole('group', { name: '透传', exact: true }).getByRole('status').getByText(labels[state.state], { exact: true }).waitFor();
      assert.equal(await page.getByRole('switch', { name: '透传', exact: true }).isChecked(), !!state.enabled && state.state !== 'unsupported' && state.state !== 'stopping');
      assert.equal(await page.getByRole('switch', { name: 'HDR', exact: true }).isChecked(), state.hdr ?? true);
      await writeFile(out + '/passthrough-state.json', JSON.stringify(state, null, 2) + '\n');
    }
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${id}: horizontal overflow`);
    const file = `${id}-light-1280.png`;
    await page.screenshot({ path: out + '/' + file, fullPage: true, animations: 'disabled' });
    captures.push(file);
    console.log('PASS page ' + id);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark' });
  for (const id of ['overview', 'video', 'output']) {
    await page.goto(base + '/#/' + id);
    await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor();
    await page.waitForFunction(() => !document.querySelector('[data-slot="skeleton"]'));
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${id}: mobile overflow`);
    const file = `${id}-dark-390.png`;
    await page.screenshot({ path: out + '/' + file, fullPage: true, animations: 'disabled' });
    captures.push(file);
  }
  assert.deepEqual(errors, [], 'no browser console errors or page exceptions');
  await writeFile(out + '/verification.json', JSON.stringify({ base, version: process.env.DEPLOY_VERSION, reads, errors, captures, writes: 'login only; no setting changes' }, null, 2) + '\n');
  await context.close();
} finally { await browser.close(); }
