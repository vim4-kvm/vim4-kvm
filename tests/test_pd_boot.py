"""Firmware handoff decisions and once-per-boot negotiation, without hardware."""
import importlib.util
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('vim4pd', Path(__file__).resolve().parents[1] / 'board/vim4pd.py')
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)


def snapshot(flags=0x41, rdo=0x1401912c, version=1):
    return struct.pack('>16I', version, flags, 0, 0, rdo, 1, 3, 5000, 3000,
                       0x2601912c, 0, 0, 0, 0, 0, 0)


class PDBootTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.handoff = self.root / 'handoff'
        self.attempt = self.root / 'attempt'
        self.run = self.enterContext(patch.object(pd.subprocess, 'run', return_value=SimpleNamespace(returncode=0)))

    def boot(self):
        return pd.bootstrap(self.handoff, self.attempt)

    def test_vendor_completed_request_without_usb_data_is_repaired_once(self):
        self.handoff.write_bytes(snapshot())
        self.assertEqual(self.boot(), 0)
        self.assertEqual(self.boot(), 0)
        self.run.assert_called_once_with(['/usr/sbin/usb-pd-init'], check=False)

    def test_existing_usb_contract_and_unconfirmed_fallback_never_negotiate(self):
        for data, reason in [
            (snapshot(rdo=0x1601912c), 'already has USB'),
            (snapshot(flags=0xd0), 'timeout or Type-C fallback'),
            (snapshot(flags=0x51), 'timeout or Type-C fallback'),
            (snapshot(flags=0x81), 'timeout or Type-C fallback'),
            (snapshot(flags=0x40), 'no PS_RDY'),
            (snapshot(flags=0x61), 'I/O error'),
            (snapshot(rdo=0), 'invalid firmware Request'),
            (snapshot(version=2), 'unsupported'),
            (snapshot()[:-1], 'length'),
        ]:
            with self.subTest(reason=reason, data=data):
                negotiate, message = pd.decision(data)
                self.assertFalse(negotiate)
                self.assertIn(reason, message)
                self.handoff.write_bytes(data)
                self.boot()
                self.attempt.unlink()
        self.run.assert_not_called()

    def test_missing_property_stays_skipped_even_if_snapshot_later_appears(self):
        self.assertEqual(self.boot(), 0)
        self.handoff.write_bytes(snapshot())
        self.assertEqual(self.boot(), 0)
        self.run.assert_not_called()

    def test_failed_negotiation_is_reported_and_never_retried_in_same_boot(self):
        self.handoff.write_bytes(snapshot())
        self.run.return_value.returncode = 7
        self.assertEqual(self.boot(), 7)
        self.assertEqual(self.boot(), 0)
        self.run.assert_called_once()
        # /run is recreated on reboot, permitting one new attempt.
        self.attempt.unlink()
        self.assertEqual(self.boot(), 7)
        self.assertEqual(self.run.call_count, 2)
