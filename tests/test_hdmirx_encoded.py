"""Raw-video pipe boundaries must not hide a truncated decoded frame."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('hdmirx_encode',
    Path(__file__).resolve().parents[1] / 'tools/hdmirx-encode-check.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class FragmentedPipe(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3))


class DecodePipeTest(unittest.TestCase):
    def test_recovery_requests_with_cyclic_refresh_reach_capture(self):
        argv = ['checker', 'capture', '--exclusive', '--encoder=wave5', '--format=nv12',
                '--output=unused.mkv', '--gop=0', '--intra-refresh-period=45',
                '--keyframe-at=60', '--keyframe-at=120']
        with mock.patch('sys.argv', argv), mock.patch.object(checker, 'capture') as capture:
            checker.main()
            self.assertEqual(capture.call_args.args[0].keyframe_at, [60, 120])

    def test_short_periodic_gop_cannot_mask_a_recovery_request(self):
        argv = ['checker', 'capture', '--exclusive', '--encoder=wave5',
                '--output=unused.mkv', '--gop=60', '--keyframe-at=60']
        with mock.patch('sys.argv', argv), mock.patch.object(checker, 'capture') as capture, \
             mock.patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                checker.main()
            capture.assert_not_called()

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

    def test_requested_high_cannot_pass_with_high10_sps(self):
        # The legacy firmware bug produced 8-bit pixels but High 10 profile.
        result = SimpleNamespace(stdout=json.dumps({'streams': [
            {'codec_name': 'h264', 'profile': 'High 10', 'width': 3840, 'height': 2160}]}))
        args = SimpleNamespace(video=Path('unused.h264'), expect_profile='High',
                               frames=240, check_colors=True)
        with mock.patch.object(checker.subprocess, 'run', return_value=result), \
             mock.patch.object(checker.subprocess, 'Popen') as decoder:
            with self.assertRaisesRegex(ValueError, 'expected encoded profile High, got High 10'):
                checker.verify(args)
            decoder.assert_not_called()
