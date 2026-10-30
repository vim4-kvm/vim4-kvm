"""Linux host execution of the actual benchmark, without board access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and shutil.which('cc') and Path('/dev/shm').exists(),
                     'requires Linux, cc and tmpfs')
class MemoryBenchTests(unittest.TestCase):
    def test_workloads_cleanup_and_page_fault_boundary(self):
        if shutil.disk_usage('/dev/shm').free < 256 * 1024 * 1024:
            self.skipTest('requires 256 MiB tmpfs headroom')
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            binary = root / 'memory-bench'
            subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'tools/memory-bench.c'), '-o', str(binary)], check=True)
            allowed = os.sched_getaffinity(0)
            command = [sys.executable, str(ROOT / 'tools/memory-bench.py'),
                       '--binary', str(binary), '--output', str(root / 'results'),
                       '--cpu', str(min(allowed)), '--repeats', '1']
            subprocess.run(command, check=True, timeout=30)
            rows = [json.loads(line) for line in (root / 'results/rows.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 35)
            self.assertTrue(all(x['cpu_begin'] == min(allowed) and x['cpu_end'] == min(allowed)
                                for x in rows))
            distribution = json.loads((root / 'results/distribution.json').read_text())
            self.assertEqual(len(distribution), 35)
            self.assertTrue(all(x['first_ns'] == x['median_ns'] for x in distribution))
            state = json.loads((root / 'results/state.json').read_text())
            self.assertEqual(state['affinity_before'], state['affinity_restored'])
            self.assertEqual(set(state['affinity_before']), allowed)
            self.assertFalse(state['timed_out'])
            first = next(x for x in rows if x['phase'] == 'anon_touch_nohuge')
            second = next(x for x in rows if x['phase'] == 'anon_retouch_nohuge')
            pages = first['size'] // os.sysconf('SC_PAGESIZE')
            self.assertGreaterEqual(first['minflt'], pages * .9)
            self.assertLess(second['minflt'], pages * .1)
            self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=5).returncode, 0)
            self.assertEqual(len(list((root / 'results').glob('*'))), 3)
            if len(allowed) > 1:
                other = max(allowed)
                alternative = command.copy()
                alternative[alternative.index('--cpu') + 1] = str(other)
                alternative[alternative.index('--output') + 1] = str(root / 'other-cpu')
                alternative[alternative.index('--repeats') + 1] = '3'
                subprocess.run(alternative, check=True, timeout=30)
                groups = json.loads((root / 'other-cpu/distribution.json').read_text())
                rows = [json.loads(line) for line in (root / 'other-cpu/rows.jsonl').read_text().splitlines()]
                self.assertTrue(all(x['cpu_begin'] == other and x['cpu_end'] == other for x in rows))
                self.assertTrue(all(x['samples'] == 3 and len(x['raw_ns']) == 3 for x in groups))
                for group in groups:
                    self.assertEqual(group['median_ns'], sorted(group['raw_ns'])[1])
