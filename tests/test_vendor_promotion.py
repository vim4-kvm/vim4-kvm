import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('vendor_promote', Path(__file__).resolve().parents[1] / 'packaging/kernel/promote.py')
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)
spec = importlib.util.spec_from_file_location('promotion_boot', Path(__file__).resolve().parents[1] / 'board/vim4boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class VendorPromotionTest(unittest.TestCase):
    def test_retirement_rejects_shared_files_and_keeps_selected_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current, old = root / 'current', root / 'old'
            current.write_bytes(b'current kernel')
            old.write_bytes(b'old kernel')
            text = ('default Default\nLABEL Default\n  LINUX /current\n'
                    'LABEL Old\n  LINUX /old\n')
            config = root / 'extlinux.conf'
            config.write_text(text)
            records = [{'label': 'Default', 'boot': {'LINUX': '/current'},
                        'artifacts': {str(current): hashlib.sha256(current.read_bytes()).hexdigest()}}]
            with patch.object(boot, 'BOOT', root), patch.object(boot, 'CONFIG', config):
                with self.assertRaises(ValueError):
                    promote.retire_entry(text, 'Default', records, boot)
                with self.assertRaises(ValueError):
                    promote.retire_entry(text + 'LABEL Shared\n  LINUX /old\n', 'Old', records, boot)
                self.assertTrue(old.exists())
                updated = promote.retire_entry(text, 'Old', records, boot)
            self.assertFalse(old.exists())
            self.assertTrue(current.exists())
            self.assertEqual(config.read_text(), updated)
            self.assertEqual(list(boot.boot_entries(updated)), ['Default'])

    def test_registration_preserves_older_records_for_same_release(self):
        original = {'abi': 1, 'kernels': [{'release': '5.15.test', 'moduleNoteSha256': '0' * 64}]}
        updated = promote.qualification_records(original, '5.15.test', b'new module')
        self.assertEqual(len(updated['kernels']), 2)
        self.assertEqual(original['kernels'][0], updated['kernels'][0])
        self.assertEqual(promote.qualification_records(updated, '5.15.test', b'new module'), updated)
        with self.assertRaises(ValueError):
            promote.qualification_records({'abi': 99}, '5.15.test', b'new module')

    def test_no_rollback_entry_is_added_when_explicitly_disabled(self):
        text = 'default Default\nLABEL Default\n  LINUX /old\n  APPEND unchanged\n'
        updated = promote.replacement(text, 'Default', {'LINUX': '/new', 'APPEND': 'unchanged'}, None, boot)
        self.assertEqual(list(boot.boot_entries(updated)), ['Default'])

    def test_profile_replacement_preserves_every_other_entry_and_arguments(self):
        text = ('default Default\nLABEL Default\n  LINUX /old\n  INITRD /old-initrd\n'
                '  FDTDIR /old-dtb\n  APPEND root=unchanged\nLABEL Stock\n  LINUX /stock\n'
                'LABEL FullKvm\n  LINUX /edge/Image\n  APPEND keep=all\n')
        fields = {'LINUX': '/new', 'INITRD': '/new-initrd', 'FDTDIR': '/new-dtb', 'APPEND': 'root=unchanged'}
        updated = promote.replacement(text, 'Default', fields, 'VendorVapb1', boot)
        self.assertIn('LABEL Stock\n  LINUX /stock\nLABEL FullKvm\n  LINUX /edge/Image\n  APPEND keep=all\n', updated)
        self.assertIn('LABEL VendorVapb1\n  LINUX /old\n  INITRD /old-initrd\n  FDTDIR /old-dtb\n  APPEND root=unchanged\n', updated)
        self.assertTrue(updated.startswith('default Default\n'))
        with self.assertRaises(ValueError):
            promote.replacement(updated, 'Default', fields, 'VendorVapb1', boot)

    def test_compression_keeps_exact_kernel_and_original_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'Image'
            original = b'kernel bytes' * 1000
            image.write_bytes(original)
            backup = root / 'backup'
            backup.mkdir()
            with patch.object(promote.subprocess, 'run'):
                checksum = promote.compress_image(image, backup)
            self.assertEqual(gzip.decompress(image.read_bytes()), original)
            self.assertEqual((backup / 'image-Image').read_bytes(), original)
            self.assertEqual(promote.digest(image), checksum)
            with self.assertRaises(FileExistsError):
                promote.compress_image(image, backup)
            self.assertEqual((backup / 'image-Image').read_bytes(), original)
