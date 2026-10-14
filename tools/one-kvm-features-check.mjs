// Authenticated terminal, local-only extension lifecycle and safe watchdog toggle.
// A loopback FRP server must already listen on 17700 with the test token below.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert(process.argv.includes('--exclusive'), 'Coordinate board access first');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const api = (path, method = 'GET', body) => page.evaluate(async ({ path, method, body }) => {
  const response = await fetch('/api/' + path, { method,
    headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
  if (!response.ok) throw new Error(path + ' HTTP ' + response.status + ': ' + await response.text());
  return response.json();
}, { path, method, body });
let originals;
let watchdog;
try {
  await page.goto('http://192.168.50.210:8080/api/setup');
  await api('auth/login', 'POST', { username: process.env.ONEKVM_USERNAME, password: process.env.ONEKVM_PASSWORD });
  originals = await api('extensions');
  for (const name of ['ttyd', 'gostc', 'easytier', 'frpc']) {
    assert(originals[name].available, name + ' unavailable');
    assert(!originals[name].config.enabled, 'Disable ' + name + ' before exclusive testing');
  }
  watchdog = await api('config/watchdog');
  assert(!watchdog.enabled, 'Watchdog already enabled; do not disturb its owner');
  await api('extensions/ttyd/config', 'PATCH', { enabled: true });
  await page.evaluate(async () => {
    for (let attempt = 0; attempt < 30; attempt++) {
      if ((await fetch('/api/terminal/')).ok) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('Terminal HTTP endpoint did not become ready');
  });
  const terminal = await page.evaluate(() => new Promise((resolve, reject) => {
    const socket = new WebSocket(`ws://${location.host}/api/terminal/ws`, 'tty');
    socket.binaryType = 'arraybuffer';
    let text = '';
    const timer = setTimeout(() => { socket.close(); reject(new Error('Terminal output timeout')); }, 10000);
    socket.onopen = () => {
      socket.send(JSON.stringify({ AuthToken: '', columns: 80, rows: 24 }));
      socket.send('0printf "VIM4_TTY_OK:%s\\n" "$(id -un)"\r');
    };
    socket.onmessage = event => {
      const bytes = new Uint8Array(event.data);
      if (bytes[0] === 48) text += new TextDecoder().decode(bytes.slice(1));
      if (text.includes('VIM4_TTY_OK:khadas')) {
        clearTimeout(timer); socket.close(); resolve('khadas');
      }
    };
    socket.onerror = () => { clearTimeout(timer); reject(new Error('Terminal websocket failed')); };
  }));
  assert.equal(terminal, 'khadas');
  await api('extensions/ttyd/stop', 'POST');
  console.log('PASS: authenticated terminal executes as khadas');

  await api('extensions/gostc/config', 'PATCH', { enabled: true, addr: '127.0.0.1:1', key: 'local-test-only', tls: false });
  await page.waitForTimeout(1500);
  assert.equal((await api('extensions/gostc')).status.state, 'running');
  await api('extensions/gostc/stop', 'POST');
  console.log('PASS: Gostc starts and stops; no external server connection tested');

  await api('extensions/easytier/config', 'PATCH', { enabled: true, config_mode: 'full', custom_toml:
    'instance_name = "onekvm-local-check"\nipv4 = "10.254.254.1/32"\nlisteners = ["tcp://127.0.0.1:0"]\n' +
    '[network_identity]\nnetwork_name = "onekvm-local-check"\nnetwork_secret = "local-test-only"\n' +
    '[flags]\ndev_name = "onekvmtest"\n' });
  let tun;
  for (let attempt = 0; attempt < 20; attempt++) {
    try { tun = JSON.parse(execFileSync('ssh', ['vim4', 'ip -j addr show dev onekvmtest'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })); break; } catch {}
    await page.waitForTimeout(500);
  }
  assert(tun?.[0]?.addr_info.some(address => address.local === '10.254.254.1'), 'EasyTier TUN not configured');
  await api('extensions/easytier/stop', 'POST');
  console.log('PASS: EasyTier creates TUN with scoped network capability');

  await api('extensions/frpc/config', 'PATCH', { enabled: true, config_mode: 'full', custom_toml:
    'serverAddr = "127.0.0.1"\nserverPort = 17700\nauth.token = "local-test-only"\n' +
    '[[proxies]]\nname = "onekvm-local-check"\ntype = "tcp"\nlocalIP = "127.0.0.1"\nlocalPort = 8080\nremotePort = 17701\n' });
  let forwarded;
  for (let attempt = 0; attempt < 20; attempt++) {
    try { forwarded = JSON.parse(execFileSync('ssh', ['vim4', 'curl --max-time 2 -fsS http://127.0.0.1:17701/api/health'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })); break; } catch {}
    await page.waitForTimeout(500);
  }
  assert.equal(forwarded?.status, 'ok');
  await api('extensions/frpc/stop', 'POST');
  console.log('PASS: FRP loopback server forwards One-KVM HTTP');

  const enabled = await api('config/watchdog', 'PATCH', { enabled: true });
  assert(enabled.running && enabled.enabled);
  await page.waitForTimeout(3000);
  assert((await api('config/watchdog')).running);
  const disabled = await api('config/watchdog', 'PATCH', { enabled: false });
  assert(!disabled.running && !disabled.enabled);
  console.log('PASS: hardware watchdog enable, feed and safe disable');
} finally {
  try {
    if (watchdog && !watchdog.enabled) await api('config/watchdog', 'PATCH', { enabled: false });
    if (originals) {
      for (const name of ['ttyd', 'gostc', 'easytier', 'frpc']) {
        if (!originals[name].config.enabled) {
          await api(`extensions/${name}/stop`, 'POST');
          // GET omits empty secrets/full-config strings; PATCH omission would
          // retain this test's values instead of restoring the empty settings.
          const emptyFields = {
            ttyd: {}, gostc: { key: '' }, easytier: { custom_toml: '' }, frpc: { custom_toml: '' },
          };
          await api(`extensions/${name}/config`, 'PATCH', { ...emptyFields[name], ...originals[name].config });
          assert.deepEqual((await api('extensions'))[name].config, originals[name].config);
        }
      }
    }
  } finally {
    if (process.argv.includes('--restore-drive')) {
      const media = await api('msd/status');
      if (media.state.mounted_count === 0) await api('msd/drive/mount', 'POST');
    }
    await browser.close();
  }
}
