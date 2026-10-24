"""Exercise the real capture loop against errors after sustained streaming."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(platform.system() == 'Linux' and shutil.which('cc'),
                     'requires Linux V4L2 headers and a C compiler')
class CaptureSoakTest(unittest.TestCase):
    def test_completions_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'soak-test'
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'tests/fixtures/hdmirx-soak-harness.c'),
                            '-o', str(binary)], check=True, capture_output=True, text=True)
            for scenario in ('success', 'error', 'gap', 'stale', 'unplug', 'stop-failure'):
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(binary), scenario], text=True,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0 if scenario == 'success' else 1,
                                     result.stderr)
                    rows = [json.loads(line) for line in result.stdout.splitlines()]
                    summary = rows[-1]
                    self.assertEqual(summary['event'], 'summary')
                    self.assertEqual(summary['success'], scenario == 'success')
                    if scenario == 'success':
                        self.assertEqual(summary['completed'], 600)
                        self.assertAlmostEqual(summary['capture_fps'], 60, places=3)
                    if scenario == 'error':
                        self.assertEqual(summary['errors'], 1)
                        self.assertEqual(summary['completed'], 250)
                        self.assertEqual(rows[-2]['sequence'], 0)
                        self.assertEqual(rows[-2]['timestamp_ns'], 0)


if __name__ == '__main__':
    unittest.main()
