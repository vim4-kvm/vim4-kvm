import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('wave5_monitor', Path(__file__).resolve().parents[1] / 'board/vim4-wave5-monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class Wave5MonitorTest(unittest.TestCase):
    def test_default_only_records_and_never_queries_or_reboots(self):
        with tempfile.TemporaryDirectory() as directory:
            state = monitor.Monitor(Path(directory))
            idle, run = Mock(), Mock()
            for now in (0, 100, 1000):
                state.step({'isolated': True}, now, idle, run)
            self.assertTrue((Path(directory) / 'alert.json').exists())
            idle.assert_not_called()
            run.assert_not_called()

    def test_reboot_requires_continuous_idle_and_is_once_per_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            state = monitor.Monitor(Path(directory), True, 30)
            idle, run = Mock(return_value=True), Mock()
            alert = {'isolated': True}
            state.step(alert, 0, idle, run)
            state.step(alert, 29, idle, run)
            run.assert_not_called()
            idle.return_value = False
            state.step(alert, 30, idle, run)
            idle.return_value = True
            state.step(alert, 31, idle, run)
            state.step(alert, 60, idle, run)
            run.assert_not_called()
            state.step(alert, 61, idle, run)
            run.assert_called_once_with(['systemctl', 'reboot'], check=True, timeout=10)
            monitor.Monitor(Path(directory), True, 30).step(alert, 1000, idle, run)
            self.assertEqual(run.call_count, 1)

    def test_unknown_active_app_or_media_prevents_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = Mock(return_value=subprocess.CompletedProcess([], 0, 'inactive\n' * 4))
            self.assertTrue(monitor.unused(run, root))
            run.return_value.stdout = '\n'.join(['inactive\n'] * 4)
            self.assertTrue(monitor.unused(run, root))
            run.return_value.stdout = 'inactive\n' * 3
            self.assertFalse(monitor.unused(run, root))
            run.return_value.stdout = 'active\n' + 'inactive\n' * 3
            self.assertFalse(monitor.unused(run, root))
            run.return_value.stdout = 'inactive\n' * 4
            lun = root / 'kvm/functions/mass_storage.disk0/lun.0/file'
            lun.parent.mkdir(parents=True)
            lun.write_text('/var/lib/vim4-kvm/disk.img\n')
            self.assertFalse(monitor.unused(run, root))

    def test_quarantine_reads_kernel_reason_and_time(self):
        with tempfile.TemporaryDirectory() as directory:
            driver = Path(directory)
            device = driver / 'fe000000.codec'
            device.mkdir()
            (device / 'isolated').write_text('0\n')
            self.assertIsNone(monitor.quarantine(driver))
            (device / 'isolated').write_text('1\n')
            self.assertIsNone(monitor.quarantine(driver))
            (device / 'isolation_reason').write_text('frame completion timeout\n')
            (device / 'isolation_time_ns').write_text('123\n')
            self.assertEqual(monitor.quarantine(driver)['timeBoottimeNs'], '123')
