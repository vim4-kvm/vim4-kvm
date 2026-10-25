import gzip
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
