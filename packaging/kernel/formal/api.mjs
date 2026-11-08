import assert from 'node:assert/strict';
import { loginManager } from '../../../tools/manager-login.mjs';
assert(process.env.BOARD_TICKET);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
try {
  const context = await browser.newContext();
  const base = 'http://127.0.0.1:18088';
  await loginManager(context, base, { localBackend: true });
  const [path, method = 'GET', body] = process.argv.slice(2);
  const options = { method, ...(body === undefined ? {} : { data: JSON.parse(body) }) };
  if (path === 'upload') {
    const fs = await import('node:fs/promises');
    options.multipart = { file: { name: 'deploy73-dedicated.img', mimeType: 'application/octet-stream', buffer: await fs.readFile(process.env.VIM4_MEDIA_IMAGE) } };
    delete options.data;
  }
  const response = await context.request.fetch(base + '/api/' + (path === 'upload' ? 'msd/images' : path), options);
  assert(response.ok(), path + ': ' + response.status() + ' ' + await response.text());
  const text = await response.text();
  console.log(text || '{}');
} finally { await browser.close(); }

