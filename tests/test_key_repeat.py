"""Exercise measurement boundaries using controlled event times, without hardware."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'requires Node.js')
class KeyRepeatTest(unittest.TestCase):
    def test_cadence_warmup_and_interrupted_holds(self):
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('tools/key-repeat.html', 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
// Run the real summarizer with event fixtures; the UI remains browser-tested.
vm.runInThisContext(source.slice(0, source.indexOf('function format(')));
function hold(interval, delay = 500) {
  const events = [{type: 'keydown', timeMs: 100, repeat: false, trusted: true}];
  for (let t = 100 + delay; t <= 6200; t += interval) {
    events.push({type: 'keydown', timeMs: t, repeat: true, trusted: true});
  }
  events.push({type: 'keyup', timeMs: 6250, repeat: false, trusted: true});
  return {events, reason: 'manual', heldAtEnd: false};
}
const direct = summarize(hold(40));
const kvm = summarize(hold(80));
assert.equal(direct.valid, true);
assert.equal(kvm.valid, true);
assert.equal(direct.sustainedHz, 25);
assert.equal(kvm.sustainedHz / direct.sustainedHz, 0.5);
assert.equal(kvm.medianIntervalMs, 80);
assert.equal(kvm.p95IntervalMs, 80);
assert.equal(kvm.firstRepeatDelayMs, 500);
assert.equal(summarize(hold(40, 900)).sustainedHz, 25);
assert.equal(summarize(hold(40, 900)).firstRepeatDelayMs, 900);

const interrupted = hold(40);
// An unexpected release, pause and new press must remain visible in cadence.
interrupted.events = interrupted.events.filter(e => e.timeMs < 2500 || e.timeMs >= 3500);
interrupted.events.push({type: 'keyup', timeMs: 2500, repeat: false, trusted: true});
interrupted.events.push({type: 'keydown', timeMs: 3500, repeat: false, trusted: true});
interrupted.events.sort((a, b) => a.timeMs - b.timeMs);
const broken = summarize(interrupted);
assert.equal(broken.valid, false);
assert.equal(broken.upCount, 2);
assert.ok(broken.sustainedHz < 22);
assert.ok(broken.maxIntervalMs >= 1000);

const blur = hold(40);
blur.reason = 'blur';
assert.equal(summarize(blur).valid, false);
const held = hold(40);
held.heldAtEnd = true;
assert.equal(summarize(held).valid, false);
const short = hold(40);
short.events = short.events.filter(e => e.timeMs < 2000);
assert.equal(summarize(short).valid, false);
assert.equal(summarize({events: [], reason: 'manual'}).sustainedHz, null);
const synthetic = hold(40);
synthetic.events[0].trusted = false;
assert.equal(summarize(synthetic).valid, false);
const modified = hold(40);
modified.events[0].modifiers = {meta: true};
assert.equal(summarize(modified).valid, false);
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
