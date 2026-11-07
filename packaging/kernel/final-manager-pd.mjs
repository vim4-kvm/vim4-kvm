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
  assert.deepEqual(power, expected.power, 'Manager PD output differs from the observed B baseline');
}
