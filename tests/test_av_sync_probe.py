"""Measurement regressions: pulse matching, warmup rejection, clock drift sign."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'requires Node.js')
class AVSyncProbeTest(unittest.TestCase):
    def test_pulse_measurements(self):
        subprocess.run(['node', '--test', 'tests/av-sync-probe.mjs'], cwd=ROOT,
                       check=True, capture_output=True, text=True, timeout=10)
