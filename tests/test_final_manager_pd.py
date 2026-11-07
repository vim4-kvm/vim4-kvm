"""Replay the real B-state manager observation without browsers or board access."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'node is required for the manager check')
class ManagerPDTest(unittest.TestCase):
    def test_captured_b_state_and_regressions(self):
        subprocess.run(['node', '--test', 'tests/final-manager-pd.mjs'],
                       cwd=ROOT, check=True, timeout=15)
