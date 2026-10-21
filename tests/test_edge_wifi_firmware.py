import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/prepare-wifi-firmware.py'
spec = importlib.util.spec_from_file_location('edge_wifi_firmware', SOURCE)
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)


class WifiFirmwareTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = []
        for index in range(3):
            data = f'firmware-{index}'.encode()
            source, target = f'input-{index}', f'alias-{index}'
            (self.root / source).write_bytes(data)
            self.files.append((source, target, hashlib.sha256(data).hexdigest()))
        patch = mock.patch.object(firmware, 'FILES', self.files)
        patch.start()
        self.addCleanup(patch.stop)

    def test_existing_aliases_remain_usable_on_repeated_preparation(self):
        firmware.prepare(self.root)
        firmware.prepare(self.root)
        for source, target, _ in self.files:
            self.assertEqual((self.root / target).readlink(), Path(source))
            self.assertEqual((self.root / target).read_bytes(), (self.root / source).read_bytes())

    def test_conflict_is_detected_before_creating_other_aliases(self):
        (self.root / 'alias-2').write_bytes(b'user file')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            firmware.prepare(self.root)
        self.assertFalse((self.root / 'alias-0').exists())
        self.assertEqual((self.root / 'alias-2').read_bytes(), b'user file')

    def test_bad_input_does_not_leave_partial_configuration(self):
        (self.root / 'input-2').write_bytes(b'wrong revision')
        with self.assertRaisesRegex(ValueError, 'Unexpected firmware'):
            firmware.prepare(self.root)
        self.assertFalse(any(self.root.glob('alias-*')))

    def test_dangling_existing_link_is_preserved_and_rejected(self):
        (self.root / 'alias-2').symlink_to('missing')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            firmware.prepare(self.root)
        self.assertEqual((self.root / 'alias-2').readlink(), Path('missing'))
        self.assertFalse((self.root / 'alias-0').exists())

    def test_failed_creation_rolls_back_only_its_own_links(self):
        (self.root / 'alias-0').symlink_to('input-0')
        original = Path.symlink_to

        def create(path, target):
            if path.name == 'alias-2':
                raise OSError('read-only filesystem')
            return original(path, target)

        with mock.patch.object(Path, 'symlink_to', create):
            with self.assertRaises(OSError):
                firmware.prepare(self.root)
        self.assertEqual((self.root / 'alias-0').readlink(), Path('input-0'))
        self.assertFalse((self.root / 'alias-1').exists())
