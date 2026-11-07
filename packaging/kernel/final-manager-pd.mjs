import assert from 'node:assert/strict';

// The baseline is an observed B-state response. It preserves the known
// unavailable kernel-PD display without turning it into a confirmed contract.
export function requireFirmwarePDState(board, power, expected) {
  const blocked = board.cmdline.split(/\s+/).filter(word => word.startsWith('module_blacklist='))
    .flatMap(word => word.slice('module_blacklist='.length).split(','));
  assert(blocked.includes('fusb302'), 'Formal B cmdline must blacklist fusb302');
  assert.equal(board.fusb302_loaded, false, 'Linux PD driver must remain unloaded');
  assert.deepEqual(board.typec_ports, [], 'B state must not create a Type-C port');
  assert.deepEqual(board.service, expected.board.service, 'PD unit must retain its successful skipped state');
  assert.deepEqual(board.service_journal, expected.board.service_journal,
    'PD unit must skip; negotiation or raw I2C fallback is not allowed');
  assert.deepEqual(Object.keys(power).sort(), Object.keys(expected.power).sort(),
    'Manager PD response must retain the B-state fields without fallback history');
  assert.equal(power.vbusPresent, null);
  assert.equal(power.bootContract, null, 'B state must not claim Linux bootstrap negotiation');
  assert.deepEqual(power.kernelPD, expected.power.kernelPD);
  assert(power.firmwarePD && typeof power.firmwarePD === 'object', 'Firmware handoff is required');
  assert.equal(power.firmwarePD.ioError, false, 'Firmware handoff reports an I/O error');
  assert.equal(power.firmwarePD.hardReset, false, 'Firmware handoff reports a hard reset');
  // U-Boot negotiates on each boot. Preserve its other fields in the caller's
  // raw evidence rather than rejecting a new Rp or a better firmware contract.
}
