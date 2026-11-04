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
        self.enterContext(patch.object(pd, 'DEVICE_TREE', self.root / 'device-tree'))

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


class KernelOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(pd, 'DEVICE_TREE', self.root))
        self.node = self.root / 'bus@fe000000/i2c@76000/typec-port@22'
        self.node.mkdir(parents=True)
        (self.node / 'compatible').write_bytes(b'fcs,fusb302\0')
        (self.node / 'reg').write_bytes(struct.pack('>I', 0x22))
        self.run = self.enterContext(patch.object(pd.subprocess, 'run'))
        self.remember = self.enterContext(patch.object(pd, 'remember_contract'))

    def test_declared_controller_excludes_legacy_even_before_driver_binds(self):
        handoff = self.root / 'khadas,usb-pd-boot'
        handoff.write_bytes(snapshot())
        self.assertTrue(pd.kernel_pd_enabled())
        self.assertEqual(pd.bootstrap(handoff, self.root / 'attempt'), 0)
        self.assertEqual(pd.linux_bootstrap(), 0)
        self.run.assert_not_called()
        self.remember.assert_not_called()

    def test_disabled_node_or_bus_and_unrelated_controller_are_not_claimed(self):
        for node in (self.node, self.node.parent, self.node.parent.parent):
            with self.subTest(node=node):
                (node / 'status').write_bytes(b'disabled\0')
                self.assertFalse(pd.kernel_pd_enabled())
                (node / 'status').unlink()
        (self.node / 'compatible').write_bytes(b'other,device\0')
        self.assertFalse(pd.kernel_pd_enabled())
        (self.node / 'compatible').write_bytes(b'fcs,fusb302\0')
        (self.node / 'reg').write_bytes(struct.pack('>I', 0x23))
        self.assertFalse(pd.kernel_pd_enabled())

    def test_vendor_bus_layout_is_also_reserved(self):
        self.node.parent.parent.rename(self.root / 'apb4@fe000000')
        self.assertTrue(pd.kernel_pd_enabled())

    def test_mainline_soc_container_and_disabled_ancestor(self):
        soc = self.root / 'soc'
        soc.mkdir()
        self.node.parent.parent.rename(soc / 'bus@fe000000')
        self.assertTrue(pd.kernel_pd_enabled())
        (soc / 'status').write_bytes(b'disabled\0')
        self.assertFalse(pd.kernel_pd_enabled())


class KernelPowerTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.node = self.root / 'dt/controller'
        self.node.mkdir(parents=True)
        self.enterContext(patch.object(pd, 'kernel_pd_node', return_value=self.node))
        self.supply = self.root / 'class/power_supply/tcpm-source-psy-9-0022'
        self.port = self.root / 'class/typec/port7'
        self.device = self.root / 'devices/controller'
        self.device.mkdir(parents=True)
        self.supply.mkdir(parents=True)
        self.port.mkdir(parents=True)
        (self.supply / 'of_node').symlink_to(self.node)
        for p in (self.supply, self.port):
            (p / 'device').symlink_to(self.device)
        (self.port / 'power_operation_mode').write_text('usb_power_delivery\n')
        (self.port / 'power_role').write_text('[sink]\n')
        self.values = {'ONLINE':'1', 'USB_TYPE':'C [PD] PD_PPS',
                       'VOLTAGE_NOW':'5000000', 'CURRENT_NOW':'1500000',
                       'VOLTAGE_MAX':'20000000', 'CURRENT_MAX':'3000000'}

    def read(self):
        (self.supply / 'uevent').write_text('\n'.join(
            'POWER_SUPPLY_'+k+'='+v for k,v in self.values.items()))
        return pd.kernel_power(self.root)

    def test_current_contract_uses_operating_values_and_matching_device(self):
        self.assertEqual(self.read(), {'state':'ready', 'contract':{'voltageV':5, 'currentA':1.5}})
        # A different Type-C port must not supply the completion state.
        (self.port / 'device').unlink()
        (self.port / 'device').symlink_to(self.root / 'unrelated')
        self.assertEqual(self.read(), {'state':'unavailable', 'contract':None})

    def test_offline_typec_fallback_or_incomplete_contract_is_not_confirmed(self):
        for key,value in [('ONLINE','0'), ('USB_TYPE','[C] PD PD_PPS'),
                          ('VOLTAGE_NOW','0'), ('CURRENT_NOW','-1')]:
            with self.subTest(key=key):
                previous = self.values[key]
                self.values[key] = value
                self.assertEqual(self.read(), {'state':'unconfirmed', 'contract':None})
                self.values[key] = previous
        (self.port / 'power_operation_mode').write_text('3.0A\n')
        self.assertIsNone(self.read()['contract'])

    def test_probe_delay_missing_and_malformed_values_keep_kernel_ownership(self):
        self.values['CURRENT_NOW'] = 'invalid'
        self.assertEqual(self.read(), {'state':'unavailable', 'contract':None})
        del self.values['CURRENT_NOW']
        self.assertEqual(self.read(), {'state':'unavailable', 'contract':None})
        (self.supply / 'of_node').unlink()
        self.assertEqual(self.read(), {'state':'unavailable', 'contract':None})
        with patch.object(pd, 'kernel_pd_node', return_value=None):
            self.assertIsNone(self.read())


class ContractHistoryTest(unittest.TestCase):
    COMPLETE = ('Request rdo 1304b12c: tx 0\n'
                'PD bootstrap complete; USB-capable 5V contract established\n'
                'PD contract at bootstrap: 5000mV 3000mA\n')

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(pd, 'DEVICE_TREE', self.root / 'device-tree'))
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
            pd.remember_linux_contract('1304b12c')
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
        def completed_tool(*args, **kwargs):
            pd.remember_linux_contract('1304b12c')
            return SimpleNamespace(returncode=0, stdout=self.COMPLETE)
        self.run.side_effect = completed_tool
        pd.bootstrap(self.handoff, self.attempt)
        self.assertEqual(json.loads(self.record.read_text())['origin'], 'linux')
        self.attempt.unlink()
        self.run.side_effect = None
        self.run.return_value.returncode = 1
        pd.bootstrap(self.handoff, self.attempt)
        record = json.loads(self.record.read_text())
        self.assertEqual(record['origin'], 'firmware')
        self.assertFalse(record['usbComm'])
        self.assertEqual(record['rdo'], '1401912c')

    def test_timeout_failed_or_incomplete_linux_does_not_replace_old_record(self):
        pd.remember_linux_contract('1304b12c')
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
        pd.remember_linux_contract('1304b12c')
        old = self.record.read_bytes()
        with patch.object(pd.os, 'replace', side_effect=OSError(5, 'I/O error')):
            pd.remember_linux_contract('1304b12c')
            self.assertEqual(pd.linux_bootstrap(), 0)
        self.assertEqual(self.record.read_bytes(), old)
        self.assertEqual(list(self.root.glob('tmp*')), [])

    def test_corrupt_incomplete_and_invalid_records_are_absent(self):
        pd.remember_linux_contract('1304b12c')
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

    def test_final_request_current_is_recorded_and_invalid_requests_preserve_history(self):
        pd.remember_linux_contract('13025896')
        record = json.loads(self.record.read_text())
        self.assertEqual(record['currentA'], 1.5)
        self.assertEqual(record['rdo'], '13025896')
        old = self.record.read_bytes()
        for value in ('garbage', '13000000', '1104b12c', '1304b096', '13064190'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pd.remember_linux_contract(value)
            self.assertEqual(self.record.read_bytes(), old)
