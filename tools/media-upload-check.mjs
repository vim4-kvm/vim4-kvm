// Real browser multipart upload plus a read-only command in the web terminal.
// Requires a trusted local session with authentication disabled or already set up.
// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node tools/media-upload-check.mjs --exclusive IMAGE [URL]
import assert from 'node:assert/strict';
import { basename, resolve } from 'node:path';

const args = process.argv.slice(2);
assert(args[0] === '--exclusive' && args[1], 'Usage: --exclusive IMAGE [URL]');
const file = resolve(args[1]);
const url = args[2] || 'http://192.168.50.210:8080';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage();
  await page.goto(url);
  // Use a native File/FormData, as the application's upload button does.
  await page.evaluate(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.id = 'media-upload-probe';
    document.body.append(input);
  });
  await page.locator('#media-upload-probe').setInputFiles(file);
  const result = await page.evaluate(async () => {
    const data = new FormData();
    data.append('file', document.querySelector('#media-upload-probe').files[0]);
    const response = await fetch('/api/download/file', { method: 'POST', body: data });
    return { status: response.status, body: await response.json() };
  });
  assert.equal(result.status, 200);
  assert.equal(result.body.code, 0, result.body.msg);
  console.log(JSON.stringify({ upload: basename(file), ...result }));

  const shell = await page.evaluate(() => new Promise((resolve, reject) => {
    const endpoint = new URL('/api/vm/terminal', location.href);
    endpoint.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(endpoint);
    ws.binaryType = 'arraybuffer';
    let output = '';
    const timer = setTimeout(() => { ws.close(); reject(new Error('terminal timed out')); }, 10000);
    ws.onopen = () => ws.send('printf "\\nVIM4_SHELL=%s\\n" "$BASH_VERSION"\r');
    ws.onmessage = ({ data }) => {
      output += typeof data === 'string' ? data : new TextDecoder().decode(data);
      const match = output.match(/VIM4_SHELL=([0-9][^\r\n]*)/);
      if (match) { clearTimeout(timer); ws.close(); resolve(match[1]); }
    };
    ws.onerror = () => { clearTimeout(timer); ws.close(); reject(new Error('terminal websocket failed')); };
  }));
  console.log(JSON.stringify({ bash: shell }));
} finally {
  await browser.close();
}
