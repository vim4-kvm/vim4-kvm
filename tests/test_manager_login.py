"""Run the shared browser login checks offline; Playwright integration is optional."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ManagerLoginTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'requires Node')
    def test_login(self):
        subprocess.run(['node', '--test', 'tests/manager-login.mjs'], check=True,
                       cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
