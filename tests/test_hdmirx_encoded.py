"""Raw-video pipe boundaries must not hide a truncated decoded frame."""
import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('hdmirx_encode',
    Path(__file__).resolve().parents[1] / 'tools/hdmirx-encode-check.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class FragmentedPipe(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3))


class DecodePipeTest(unittest.TestCase):
    def test_short_reads_still_form_whole_frames(self):
        pipe = FragmentedPipe(b'abcdefghABCDEFGH')
        self.assertEqual(checker.read_frame(pipe, 8), b'abcdefgh')
        self.assertEqual(checker.read_frame(pipe, 8), b'ABCDEFGH')
        self.assertIsNone(checker.read_frame(pipe, 8))

    def test_partial_final_frame_fails(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            checker.read_frame(FragmentedPipe(b'abcde'), 8)

    def test_empty_clip_has_clean_eof(self):
        self.assertIsNone(checker.read_frame(io.BytesIO(), 8))
