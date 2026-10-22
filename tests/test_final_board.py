"""A source/EDID transition is transient; a persistently broken link is not."""
import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    'final_board', Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/final-board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class StatusRecoveryTest(unittest.TestCase):
    def test_edid_restore_may_relock_after_multiple_status_reads(self):
        path = Mock()
        path.read_text.side_effect = ['source_5v: 1\nlink_ready: 0\n'] * 2 + [
            'source_5v: 1\nlink_ready: 1\n']
        with patch.object(board.time, 'monotonic', side_effect=[0, .1, .2]), \
                patch.object(board.time, 'sleep'):
            value = board.wait_for_status(path, ['source_5v: 1', 'link_ready: 1'])
        self.assertIn('link_ready: 1', value)
        self.assertEqual(path.read_text.call_count, 3)

    def test_persistent_loss_or_capture_fault_expires_with_last_evidence(self):
        for status, required in [('link_ready: 0', ['link_ready: 1']),
                                 ('faulted: 1\nstream_error: 0', ['faulted: 0', 'stream_error: 0'])]:
            with self.subTest(status=status):
                path = Mock()
                path.read_text.return_value = status
                with patch.object(board.time, 'monotonic', side_effect=[0, .1, 1.1]), \
                        patch.object(board.time, 'sleep'), \
                        self.assertRaisesRegex(RuntimeError, 'did not recover within 1s') as error:
                    board.wait_for_status(path, required, timeout=1)
                self.assertIn(status, str(error.exception))


class ModuleRecoveryTest(unittest.TestCase):
    def test_same_release_partial_install_restores_original_directory(self):
        for phase in ('before-rename', 'after-rename', 'after-install'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                modules, backup = root / 'modules', root / 'backup'
                modules.mkdir()
                backup.mkdir()
                (modules / 'baseline.ko').write_bytes(b'original BTF')
                (backup / 'state.json').write_text(json.dumps({'modules': board.tree(modules)}))
                if phase != 'before-rename':
                    modules.rename(backup / 'original-modules')
                if phase == 'after-install':
                    modules.mkdir()
                    (modules / 'candidate.ko').write_bytes(b'new BTF')
                instance = object.__new__(board.Board)
                instance.baseline = {'release': board.RELEASE}
                instance.backup = backup
                with patch.object(board, 'MODULES', modules):
                    instance.restore_modules()
                self.assertEqual((modules / 'baseline.ko').read_bytes(), b'original BTF')
                self.assertFalse((modules / 'candidate.ko').exists())
                if phase == 'after-install':
                    self.assertEqual((backup / 'candidate-modules/candidate.ko').read_bytes(), b'new BTF')


if __name__ == '__main__':
    unittest.main()
