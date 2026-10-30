"""USB preparation must preserve live gadgets and refuse unrelated owners."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/one-kvm-edge-usb-prepare'
loader = importlib.machinery.SourceFileLoader('edge_usb', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
usb = importlib.util.module_from_spec(spec)
loader.exec_module(usb)


class EdgeUsbTest(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = root / 'gadgets'
        self.root.mkdir()
        self.marker = root / 'prepared'
        address = root / 'ethernet-address'
        address.write_text('c8:63:14:74:70:0d\n')
        self.enterContext(patch.object(usb, 'ETHERNET_ADDRESS', address))
        self.enterContext(patch.object(usb, 'ROOT', self.root))
        self.enterContext(patch.object(usb, 'MARKER', self.marker))
        self.enterContext(patch.object(usb.os, 'geteuid', return_value=0))
        self.enterContext(patch.object(usb.platform, 'release', return_value='7.3.0-vim4kvm-uhd1+'))
        self.run = self.enterContext(patch.object(usb.subprocess, 'run'))

    def existing(self):
        gadget = self.root / 'kvm'
        for name, *_ in usb.HIDS:
            (gadget / 'functions' / ('hid.' + name)).mkdir(parents=True)
        lun = gadget / 'functions/mass_storage.disk0/lun.0'
        lun.mkdir(parents=True)
        (lun / 'file').write_text('\n')
        (gadget / 'UDC').write_text('fdd00000.usb\n')
        self.marker.write_text(usb.SERIAL)
        usb.prepare_optional_functions(gadget)
        return gadget

    def test_repeated_prepare_does_not_rebind_or_modify_open_hid_instances(self):
        gadget = self.existing()
        before = {p: p.read_bytes() for p in gadget.rglob('*') if p.is_file()}
        usb.prepare()
        self.assertEqual(before, {p: p.read_bytes() for p in gadget.rglob('*') if p.is_file()})
        self.run.assert_not_called()

    def test_npu_candidate_preserves_live_gadget_without_input_or_rebind(self):
        gadget = self.existing()
        before = {p: p.read_bytes() for p in gadget.rglob('*') if p.is_file()}
        for release in ('7.3.0-vim4kvm-npu1+', '7.3.0-vim4kvm-uhd2+', '7.3.0-vim4kvm-uhd2-nodebug+'):
            with self.subTest(release=release), patch.object(usb.platform, 'release', return_value=release):
                usb.prepare()
                self.assertEqual(before, {p: p.read_bytes() for p in gadget.rglob('*') if p.is_file()})
                self.run.assert_not_called()

    def test_foreign_and_unmarked_gadgets_are_refused_before_module_loading(self):
        for name in ('other-application', 'kvm'):
            with self.subTest(name=name):
                gadget = self.root / name
                gadget.mkdir()
                (gadget / 'UDC').write_text('controller')
                with self.assertRaisesRegex(ValueError, 'unrecognized'):
                    usb.prepare()
                self.assertEqual((gadget / 'UDC').read_text(), 'controller')
                (gadget / 'UDC').unlink()
                gadget.rmdir()
        self.run.assert_not_called()

    def test_mounted_media_survives_repeated_prepare_without_unbinding(self):
        gadget = self.existing()
        backing = gadget / 'functions/mass_storage.disk0/lun.0/file'
        backing.write_text('/user/disk.img\n')
        usb.prepare()
        self.assertEqual(backing.read_text(), '/user/disk.img\n')
        self.assertEqual((gadget / 'UDC').read_text(), 'fdd00000.usb\n')
        self.run.assert_not_called()

    def test_hid_only_upgrade_adds_unlinked_functions_without_reenumeration(self):
        gadget = self.existing()
        for name in ('ncm.usb0', 'uac2.usb0'):
            function = gadget / 'functions' / name
            for child in function.iterdir():
                child.unlink()
            function.rmdir()
        usb.prepare()
        self.assertEqual((gadget / 'UDC').read_text(), 'fdd00000.usb\n')
        self.assertFalse((gadget / 'configs/c.1').exists())
        network = gadget / 'functions/ncm.usb0'
        self.assertEqual((network / 'host_addr').read_text(), '02:63:14:74:70:0d')
        self.assertEqual((network / 'dev_addr').read_text(), '06:63:14:74:70:0d')
        self.assertEqual((gadget / 'functions/uac2.usb0/p_srate').read_text(), '48000')
        self.assertEqual((gadget / 'functions/uac2.usb0/c_chmask').read_text(), '0')
        self.run.assert_not_called()

    def test_production_kernel_cannot_touch_gadgets(self):
        with patch.object(usb.platform, 'release', return_value='5.15.137-vim4kvm'):
            with self.assertRaisesRegex(ValueError, 'matched 7.3'):
                usb.prepare()
        self.assertEqual(list(self.root.iterdir()), [])
        self.run.assert_not_called()
