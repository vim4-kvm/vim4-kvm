import configparser
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('packages', ROOT / 'packaging/ubuntu/package.py')
packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packages)


class WatchdogPolicyTests(unittest.TestCase):
    def test_board_package_installs_shared_pid1_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            real_copy = packages.copy

            def copy(source, target, destination, mode=0o644):
                # Exercise the real packaged watchdog payload while leaving
                # unrelated optional application build artifacts out of scope.
                if str(source).endswith('60-vim4-watchdog.conf'):
                    return real_copy(source, target, destination, mode)
                return packages.write(target, destination, '', mode)

            with patch.object(packages, 'ROOT', ROOT), patch.object(packages, 'copy', copy):
                packages.board(stage)
            config = stage / 'usr/lib/systemd/system.conf.d/60-vim4-watchdog.conf'
            policy = configparser.ConfigParser()
            policy.read(config)
            runtime = policy['Manager']['RuntimeWatchdogSec']
            reboot = policy['Manager']['RebootWatchdogSec']
            self.assertEqual(runtime, '30s')
            self.assertEqual(reboot, '60s')
            self.assertLessEqual(int(reboot[:-1]), 65)  # T7 16-bit millisecond counter.
            self.assertEqual(config.read_bytes(), (ROOT / 'board/60-vim4-watchdog.conf').read_bytes())
            self.assertEqual(config.stat().st_mode & 0o777, 0o644)
            self.assertIn('60-vim4-watchdog.conf /usr/lib/systemd/system.conf.d/',
                          (ROOT / 'board/install.sh').read_text())


if __name__ == '__main__':
    unittest.main()
