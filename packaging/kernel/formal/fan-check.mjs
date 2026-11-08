// Authenticated API write/readback against the six real thermal-zone trip tables.
// Restores both the original trips and the original config's presence/content.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { loginManager } from '../../../tools/manager-login.mjs';
assert(process.env.BOARD_TICKET, 'Requires the approved board ticket');
execFileSync('tools/board-queue', ['sampling', 'on']);
const url = process.env.MANAGER_URL || 'http://192.168.50.210';
const program = `import json,os
from pathlib import Path
fan=next(p for p in Path('/sys/class/thermal').glob('cooling_device*') if (p/'type').read_text().strip()=='khadas-mcu-fan')
zones={}
for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
 kind=(zone/'type').read_text().strip()
 if kind not in ('a73-thermal','a53-thermal','gpu-thermal','nna-thermal','vpu-thermal','hevc-thermal'):continue
 ids=sorted({int(Path(str(p)+'_trip_point').read_text()) for p in zone.glob('cdev*') if p.is_symlink() and p.resolve()==fan.resolve()})
 assert len(ids)==15
 assert (zone/'policy').read_text().strip()=='step_wise'
 assert (zone/'mode').read_text().strip()=='enabled'
 zones[kind]=[int((zone/('trip_point_'+str(i)+'_temp')).read_text()) for i in ids]
assert len(zones)==6
config=Path('/etc/default/vim4-kvm-fan')
print(json.dumps(dict(zones=zones,config=config.read_bytes().hex() if config.exists() else None,mode=config.stat().st_mode&0o777 if config.exists() else None)))
`;
const sshPython = text => execFileSync('ssh', ['-oBatchMode=yes', '-oConnectTimeout=5', process.env.VIM4_HOST || 'vim4', 'sudo -n python3 -'],
  { input: text, encoding: 'utf8', timeout: 30000 });
const before = JSON.parse(sshPython(program));
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
let context, page, original, attempted = false;
async function applyThroughPanel(target) {
  await page.goto(url + '/#/cooling');
  const inputs = page.getByRole('spinbutton');
  await inputs.first().waitFor();
  assert.equal(await inputs.count(), 3);
  for (const [index, key] of ['low', 'mid', 'high'].entries()) {
    await inputs.nth(index).fill(String(target[key]));
  }
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url() === url + '/api/fan-curve' && r.request().method() === 'POST'),
    page.getByRole('button', { name: '应用曲线', exact: true }).click(),
  ]);
  assert(response.ok(), 'Panel fan save must accept the valid curve');
  await page.reload();
  for (const [index, key] of ['low', 'mid', 'high'].entries()) {
    await inputs.nth(index).waitFor();
    assert.equal(await inputs.nth(index).inputValue(), String(target[key]));
  }
}
try {
  context = await browser.newContext();
  await context.addInitScript(() => localStorage.setItem('vim4-manager-language', 'zh-CN'));
  await loginManager(context, url);
  page = await context.newPage();
  const statusResponse = await context.request.get(url + '/api/status');
  assert(statusResponse.ok());
  original = (await statusResponse.json()).hardware.fanTriggers;
  assert(original);
  const target = JSON.stringify(original) === JSON.stringify({ low: 65, mid: 85, high: 100 })
    ? { low: 60, mid: 80, high: 100 } : { low: 65, mid: 85, high: 100 };
  attempted = true;
  await applyThroughPanel(target);
  await page.screenshot({ path: process.env.VIM4_FINAL_LOGS + '/manager-fan-saved.png', fullPage: true });
  const changed = JSON.parse(sshPython(program));
  const tables = Object.values(changed.zones);
  assert(tables.every(table => JSON.stringify(table) === JSON.stringify(tables[0])));
  assert.deepEqual([tables[0][6], tables[0][10], tables[0][14]], [target.low, target.mid, target.high].map(x => x * 1000));
  const readback = await context.request.get(url + '/api/status');
  assert(readback.ok());
  const hardware = (await readback.json()).hardware;
  assert.deepEqual(hardware.fanTriggers, target);
  assert.deepEqual(hardware.fanCurve.map(p => p.tempC * 1000), tables[0]);
  assert.equal(hardware.fanAuto, true);
  console.log(JSON.stringify({ phase: 'fan-api-write-readback', target, hardware, zones: changed.zones }));
} finally {
  try {
    if (attempted) {
      const restore = `import os,subprocess
from pathlib import Path
subprocess.run(['/usr/libexec/vim4-manager-helper','fan-curve',${[original.low, original.mid, original.high].map(v => JSON.stringify(String(v))).join(',')}],check=True)
path=Path('/etc/default/vim4-kvm-fan')
content=${before.config === null ? 'None' : JSON.stringify(before.config)}
if content is None:path.unlink(missing_ok=True)
else:
 path.write_bytes(bytes.fromhex(content))
 path.chmod(${before.mode ?? 420})
os.sync()
`;
      try {
        await applyThroughPanel(original);
      } finally {
        sshPython(restore);
        const after = JSON.parse(sshPython(program));
        assert.deepEqual(after, before, 'Fan trips and persistent config must be restored exactly');
        console.log(JSON.stringify({ phase: 'fan-api-restored', passed: true }));
      }
    }
  } finally {
    await browser.close();
  }
}

