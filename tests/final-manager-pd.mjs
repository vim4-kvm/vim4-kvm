import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { requireFirmwarePDState } from '../packaging/kernel/final-manager-pd.mjs';

const observed = JSON.parse(await readFile(new URL('../packaging/kernel/pd-b-state.json', import.meta.url), 'utf8'));

test('captured formal B state shows the firmware handoff without inventing a contract', () => {
  requireFirmwarePDState(observed.board, observed.power, observed);
});

test('a better firmware 5V/3A contract and changed Rp remain valid B state', () => {
  const power = structuredClone(observed.power);
  Object.assign(power.firmwarePD, { contract: { voltageV: 5, currentA: 3 },
    psReady: true, timedOut: false, typecFallback: false, rp: 'default' });
  requireFirmwarePDState(observed.board, power, observed);
});

test('loaded TCPM, a Type-C port or missing blacklist rejects B state', () => {
  for (const mutate of [
    board => { board.fusb302_loaded = true; },
    board => { board.typec_ports = ['port0']; },
    board => { board.cmdline = board.cmdline.replace('module_blacklist=fusb302', ''); },
  ]) {
    const board = structuredClone(observed.board);
    mutate(board);
    assert.throws(() => requireFirmwarePDState(board, observed.power, observed));
  }
});

test('unit failure and bootstrap fallback reject even with the original skipped line', () => {
  const failed = structuredClone(observed.board);
  failed.service.Result = 'exit-code';
  failed.service.ActiveState = 'failed';
  assert.throws(() => requireFirmwarePDState(failed, observed.power, observed));
  const fallback = structuredClone(observed.board);
  fallback.service_journal += 'PD bootstrap repair: requesting USB-capable 5V\n';
  assert.throws(() => requireFirmwarePDState(fallback, observed.power, observed));
});

test('I2C errors and claimed Linux contracts cannot masquerade as unchanged firmware handoff', () => {
  for (const mutate of [
    power => { power.firmwarePD.ioError = true; },
    power => { power.bootContract = { voltageV: 5, currentA: 3 }; },
    power => { power.kernelPD = { state: 'ready', contract: { voltageV: 5, currentA: 3 } }; },
    power => { power.kernelPD = { state: 'unavailable', contract: null }; },
    power => { power.firmwarePD.hardReset = true; },
    power => { power.vbusPresent = true; },
    power => { power.lastContract = { voltageV: 5, currentA: 3 }; },
  ]) {
    const power = structuredClone(observed.power);
    mutate(power);
    assert.throws(() => requireFirmwarePDState(observed.board, power, observed));
  }
});
