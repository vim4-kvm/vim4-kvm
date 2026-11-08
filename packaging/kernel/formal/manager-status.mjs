// Print vim4-manager /api/status through the executor's SSH forward (MANAGER_URL).
// The One-KVM backend behind api.mjs has no /api/status; PD power fields live here.
import assert from 'node:assert/strict';
import { loginManager } from '../../../tools/manager-login.mjs';
assert(process.env.BOARD_TICKET && process.env.MANAGER_URL);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
try {
  const context = await browser.newContext();
  await loginManager(context, process.env.MANAGER_URL);
  const response = await context.request.get(process.env.MANAGER_URL + '/api/status');
  assert(response.ok(), 'status: ' + response.status() + ' ' + await response.text());
  console.log(await response.text());
} finally { await browser.close(); }
