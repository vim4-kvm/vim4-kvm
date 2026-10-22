import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('vim4boot', Path(__file__).resolve().parents[1] / 'board/vim4boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class BootSelectionTest(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.directory)
        self.config = self.root / 'extlinux.conf'
        self.original = ('menu background /splash.bmp\nLABEL Default\n  LINUX /Image\n'
                         '  APPEND root=unchanged\n\ntimeout 5\ndefault Default\n\n'
                         'LABEL FullKvm\n  LINUX /edge/Image\n  FDT /edge/vim4.dtb\n'
                         '  APPEND root=unchanged vim4.full_kvm=1\n')
        self.config.write_text(self.original)
        image = self.root / 'Image'
        image.write_bytes(b'installed kernel')
        entries = []
        for identifier, label in (('vendor', 'Default'), ('mainline', 'FullKvm')):
            entries.append({'id': identifier, 'label': label,
                            'boot': boot.boot_entries(self.original)[label],
                            'artifacts': {str(image): hashlib.sha256(image.read_bytes()).hexdigest()}})
        self.enterContext(patch.object(boot, 'BOOT', self.root))
        self.enterContext(patch.object(boot, 'CONFIG', self.config))
        self.enterContext(patch.object(boot, 'installed', return_value=entries))

    def test_roundtrip_only_changes_default_and_keeps_recovery_copy(self):
        boot.select('mainline')
        self.assertEqual(self.config.read_text(), self.original.replace('default Default', 'default FullKvm'))
        backup = self.config.with_name('extlinux.conf.before-kernel-switch')
        self.assertEqual(backup.read_text(), self.original)
        boot.select('mainline')
        self.assertEqual(backup.read_text(), self.original)
        boot.select('vendor')
        self.assertEqual(self.config.read_text(), self.original)

    def test_corrupted_or_missing_artifact_never_changes_boot_selection(self):
        for content in (b'corrupt', None):
            image = self.root / 'Image'
            if content is None:
                image.unlink()
            else:
                image.write_bytes(content)
            with self.assertRaises(ValueError):
                boot.select('mainline')
            self.assertEqual(self.config.read_text(), self.original)

    def test_modified_arguments_and_unknown_selection_are_rejected(self):
        changed = self.original.replace('vim4.full_kvm=1', 'systemd.mask=vim4-manager.service')
        self.config.write_text(changed)
        for identifier in ('mainline', 'mainline\nLABEL injected', 'unknown'):
            with self.assertRaises(ValueError):
                boot.select(identifier)
            self.assertEqual(self.config.read_text(), changed)

    def test_ambiguous_default_cannot_be_overwritten(self):
        self.config.write_text(self.original + '\ndefault FullKvm\n')
        with self.assertRaises(ValueError):
            boot.select('mainline')
