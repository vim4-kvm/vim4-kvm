import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'wifi_coredump', ROOT / 'packaging/kernel-edge/save-wifi-coredump.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class WifiCoredumpTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.device = self.root / 'devcd0'
        (self.device / 'failing_device').mkdir(parents=True)
        self.driver = self.root / 'brcmfmac'
        self.driver.mkdir()
        (self.device / 'failing_device/driver').symlink_to(self.driver)
        (self.device / 'data').write_bytes(b'firmware evidence')
        self.destination = self.root / 'saved'

    def test_durable_evidence_precedes_acknowledgement_and_retention_is_bounded(self):
        for index in range(3):
            payload = f'firmware evidence {index}'.encode()
            (self.device / 'data').write_bytes(payload)
            result = collector.save_dump(self.device, self.destination, '7.3-test')
            path = Path(result['path'])
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(json.loads(path.with_suffix('.json').read_text())['sha256'],
                             result['sha256'])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual((self.device / 'data').read_bytes(), b'1')
        self.assertEqual(len(list(self.destination.glob('*.bin'))), 2)
        self.assertEqual(len(list(self.destination.glob('*.json'))), 2)

    def test_production_kernel_and_other_drivers_are_untouched(self):
        self.assertIsNone(collector.save_dump(self.device, self.destination, '5.15-test'))
        self.driver.rename(self.root / 'other-driver')
        (self.device / 'failing_device/driver').unlink()
        (self.device / 'failing_device/driver').symlink_to(self.root / 'other-driver')
        self.assertIsNone(collector.save_dump(self.device, self.destination, '7.3-test'))
        self.assertEqual((self.device / 'data').read_bytes(), b'firmware evidence')
        self.assertFalse(self.destination.exists())

    def test_failed_save_keeps_kernel_dump_available(self):
        self.destination.write_text('not a directory')
        with self.assertRaises(OSError):
            collector.save_dump(self.device, self.destination, '7.3-test')
        self.assertEqual((self.device / 'data').read_bytes(), b'firmware evidence')

    def test_wifi_removal_before_udev_does_not_lose_the_retained_dump(self):
        (self.device / 'failing_device/driver').unlink()
        (self.device / 'failing_device').rmdir()
        (self.device / 'failing_device').symlink_to(self.root / 'mmc2:0001:1')
        result = collector.save_dump(self.device, self.destination, '7.3-test')
        self.assertEqual(Path(result['path']).read_bytes(), b'firmware evidence')
        self.assertEqual((self.device / 'data').read_bytes(), b'1')

    def test_oversized_dump_is_not_acknowledged(self):
        original = collector.MAX_BYTES
        self.addCleanup(setattr, collector, 'MAX_BYTES', original)
        collector.MAX_BYTES = 4
        with self.assertRaises(ValueError):
            collector.save_dump(self.device, self.destination, '7.3-test')
        self.assertEqual((self.device / 'data').read_bytes(), b'firmware evidence')


if __name__ == '__main__':
    unittest.main()
