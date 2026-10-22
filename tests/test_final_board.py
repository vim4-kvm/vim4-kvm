"""A source/EDID transition is transient; a persistently broken link is not."""
import importlib.util
from pathlib import Path
import unittest
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


if __name__ == '__main__':
    unittest.main()
