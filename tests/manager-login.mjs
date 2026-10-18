import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { test } from 'node:test';
import { loginManager } from '../tools/manager-login.mjs';

test('manager login rejects missing credentials and never reports response secrets', async () => {
  const previous = process.env.MANAGER_PASSWORD;
  try {
    delete process.env.MANAGER_PASSWORD;
    await assert.rejects(loginManager({}, 'http://127.0.0.1:8080'), /Set MANAGER_PASSWORD/);
    process.env.MANAGER_PASSWORD = 'fixture-secret';
    const context = { request: { post: async () => ({ ok: () => false, status: () => 401 }) } };
    await assert.rejects(loginManager(context, 'http://127.0.0.1:8080'), /^Error: Manager login failed: HTTP 401$/);
    context.request.post = async () => ({ ok: () => true });
    context.cookies = async () => [];
    await assert.rejects(loginManager(context, 'http://127.0.0.1:8080'), /did not set a vim4_session/);
  } finally {
    if (previous === undefined) delete process.env.MANAGER_PASSWORD;
    else process.env.MANAGER_PASSWORD = previous;
  }
});

test('the login cookie reaches pages in the same BrowserContext', async t => {
  let chromium;
  try {
    ({ chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright'));
  } catch {
    t.skip('Set PLAYWRIGHT_MODULE to run the browser cookie integration check');
    return;
  }
  const previous = process.env.MANAGER_PASSWORD;
  process.env.MANAGER_PASSWORD = 'fixture-secret';
  const failures = [];
  let origin;
  const server = createServer(async (request, response) => {
    try {
      if (request.url === '/__vim4/api/auth/login') {
        assert.equal(request.method, 'POST');
        assert.equal(request.headers.origin, origin);
        assert.equal(request.headers['content-type'], 'application/json');
        let body = '';
        for await (const chunk of request) body += chunk;
        assert.deepEqual(JSON.parse(body), {
          username: process.env.MANAGER_USERNAME || 'admin', password: 'fixture-secret',
        });
        response.setHeader('Set-Cookie', 'vim4_session=fixture-token; Path=/; HttpOnly; SameSite=Strict');
        response.end('{}');
      } else {
        assert.match(request.headers.cookie || '', /vim4_session=fixture-token/);
        response.end('Authenticated viewer');
      }
    } catch (error) {
      failures.push(error);
      response.writeHead(500).end();
    }
  });
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    origin = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const context = await browser.newContext();
    await loginManager(context, origin + '/ignored/path');
    const page = await context.newPage();
    assert.equal((await page.goto(origin + '/viewer')).status(), 200);
    assert.deepEqual(failures, []);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
    if (previous === undefined) delete process.env.MANAGER_PASSWORD;
    else process.env.MANAGER_PASSWORD = previous;
  }
});
