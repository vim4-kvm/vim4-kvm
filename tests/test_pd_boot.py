"""Firmware handoff decisions and once-per-boot negotiation, without hardware."""
import importlib.util
import json
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
        self.run = self.enterContext(patch.object(pd.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='')))
        self.enterContext(patch.object(pd, 'remember_contract'))

    def boot(self):
        return pd.bootstrap(self.handoff, self.attempt)

    def test_vendor_completed_request_without_usb_data_is_repaired_once(self):
        self.handoff.write_bytes(snapshot())
        self.assertEqual(self.boot(), 0)
        self.assertEqual(self.boot(), 0)
        self.run.assert_called_once_with(['/usr/sbin/usb-pd-init'], check=False,
                                         stdout=pd.subprocess.PIPE, text=True)

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


class ContractHistoryTest(unittest.TestCase):
    COMPLETE = ('Request rdo 1304b12c: tx 0\n'
                'PD bootstrap complete; USB-capable 5V contract established\n'
                'PD contract at bootstrap: 5000mV 3000mA\n')

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.record = self.root / 'pd-last-contract.json'
        self.boot_id = self.root / 'boot-id'
        self.boot_id.write_text('first-boot\n')
        self.handoff = self.root / 'khadas,usb-pd-boot'
        self.attempt = self.root / 'attempt'
        self.save = pd.remember_contract
        self.enterContext(patch.object(pd, 'remember_contract', side_effect=lambda *args:
            self.save(*args, path=self.record, boot_id=self.boot_id)))
        self.run = self.enterContext(patch.object(pd.subprocess, 'run',
            return_value=SimpleNamespace(returncode=0, stdout=self.COMPLETE)))

    def previous(self):
        return pd.previous_contract(self.record, self.boot_id)

    def test_confirmed_linux_is_atomic_and_only_visible_across_boots(self):
        with patch.object(pd.os, 'replace', wraps=pd.os.replace) as replace:
            pd.linux_bootstrap()
        replace.assert_called_once()
        source, destination = replace.call_args.args
        self.assertEqual(Path(source).parent, destination.parent)
        self.assertEqual(list(self.root.glob('tmp*')), [])
        self.assertIsNone(self.previous())
        self.boot_id.write_text('second-boot')
        record = self.previous()
        self.assertEqual((record['voltageV'], record['currentA'], record['rdo'],
                          record['usbComm'], record['origin']), (5, 3, '1304b12c', True, 'linux'))
        self.assertIsNotNone(pd.datetime.fromisoformat(record['establishedAt']).utcoffset())

    def test_firmware_saved_before_repair_and_linux_takes_precedence(self):
        # Valid PS_RDY firmware request lacking USB comm, followed by Linux repair.
        self.handoff.write_bytes(struct.pack('>16I', 1, 0x41, 0x1061, 0x1042,
            0x1401912c, 1, 3, 5000, 3000, 0x2601912c, 0, 0, 0, 0, 0, 0))
        pd.bootstrap(self.handoff, self.attempt)
        self.assertEqual(json.loads(self.record.read_text())['origin'], 'linux')
        self.attempt.unlink()
        self.run.return_value.returncode = 1
        pd.bootstrap(self.handoff, self.attempt)
        record = json.loads(self.record.read_text())
        self.assertEqual(record['origin'], 'firmware')
        self.assertFalse(record['usbComm'])
        self.assertEqual(record['rdo'], '1401912c')

    def test_timeout_failed_or_incomplete_linux_does_not_replace_old_record(self):
        pd.linux_bootstrap()
        old = self.record.read_bytes()
        self.handoff.write_bytes(snapshot(flags=0xd0))
        self.run.reset_mock()
        pd.bootstrap(self.handoff, self.attempt)
        self.run.assert_not_called()
        for code, log in ((1, self.COMPLETE), (0, 'Request rdo 1304b12c: tx 0\n')):
            self.run.return_value = SimpleNamespace(returncode=code, stdout=log)
            pd.linux_bootstrap()
        self.assertEqual(self.record.read_bytes(), old)

    def test_confirmed_firmware_with_usb_data_is_saved_without_negotiation(self):
        self.handoff.write_bytes(struct.pack('>16I', 1, 0x41, 0x1061, 0x1042,
            0x1601912c, 1, 3, 5000, 3000, 0x2601912c, 0, 0, 0, 0, 0, 0))
        pd.bootstrap(self.handoff, self.attempt)
        record = json.loads(self.record.read_text())
        self.assertEqual(record['origin'], 'firmware')
        self.assertTrue(record['usbComm'])
        self.run.assert_not_called()

    def test_failed_atomic_replace_preserves_history_and_linux_exit_status(self):
        pd.linux_bootstrap()
        old = self.record.read_bytes()
        with patch.object(pd.os, 'replace', side_effect=OSError(5, 'I/O error')):
            self.assertEqual(pd.linux_bootstrap(), 0)
        self.assertEqual(self.record.read_bytes(), old)
        self.assertEqual(list(self.root.glob('tmp*')), [])

    def test_corrupt_incomplete_and_invalid_records_are_absent(self):
        pd.linux_bootstrap()
        record = json.loads(self.record.read_text())
        self.boot_id.write_text('second-boot')
        for field in record:
            incomplete = dict(record)
            del incomplete[field]
            self.record.write_text(json.dumps(incomplete))
            self.assertIsNone(self.previous(), field)
        for data in ('{', '[]', 'null', json.dumps(dict(record, establishedAt='2026-10-22T12:00:00')),
                     json.dumps(dict(record, usbComm='yes')), json.dumps(dict(record, voltageV=-5))):
            self.record.write_text(data)
            self.assertIsNone(self.previous())
        self.record.unlink()
        self.assertIsNone(self.previous())
