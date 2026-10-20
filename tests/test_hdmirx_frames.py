"""Reject torn, corrupted and stale experimental HDMI snapshots."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'frames', Path(__file__).resolve().parents[1] / 'tools/hdmirx-frame-check.py')
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


def image(words):
    raw = bytearray(1920 * 1080 * 3)
    for y, word in zip((85, 540, 995), words):
        for bit in range(32):
            x = int(20 + (bit + .5) * 1880 / 32)
            offset = (y * 1920 + x) * 3
            raw[offset:offset + 3] = bytes([255 if word & (1 << (31 - bit)) else 0]) * 3
    return raw


class FrameTests(unittest.TestCase):
    def test_complete_frame(self):
        result = frames.decode_frame(image([0xa5123483] * 3))
        self.assertEqual(result['id'], 0x1234)

    def test_empty_or_truncated_capture(self):
        for raw in (b'', bytes(1920 * 1080 * 3 - 1)):
            with self.assertRaisesRegex(ValueError, 'expected'):
                frames.decode_frame(raw)

    def test_torn_frame(self):
        with self.assertRaisesRegex(ValueError, 'disagree'):
            frames.decode_frame(image([0xa50001a4, 0xa50002a7, 0xa50001a4]))

    def test_channel_corruption_despite_decodable_id(self):
        raw = image([0xa5123483] * 3)
        # First marker cell is white. Its green component alone is broken.
        raw[(85 * 1920 + 49) * 3 + 1] = 0
        with self.assertRaisesRegex(ValueError, 'corrupt black/white'):
            frames.decode_frame(raw)

    def test_wrong_checksum(self):
        with self.assertRaisesRegex(ValueError, 'invalid marker'):
            frames.decode_frame(image([0xa5123482] * 3))

    def test_progress_and_counter_wrap(self):
        frames.check_advance(50, 53)
        frames.check_advance(65535, 0)
        for previous, current in ((50, 50), (50, 49)):
            with self.assertRaisesRegex(ValueError, 'did not advance'):
                frames.check_advance(previous, current)

    def test_uhd_nv12_dimensions_and_neutral_chroma(self):
        width, height = 3840, 2160
        raw = bytearray([16]) * (width * height) + bytearray([128]) * (width * height // 2)
        for y in (170, 1080, 1990):
            for bit in range(32):
                x = int((20 + (bit + .5) * 1880 / 32) * 2)
                raw[y * width + x] = 235 if 0xa5123483 & (1 << (31 - bit)) else 16
        self.assertEqual(frames.decode_frame(raw, width, height, 'nv12')['id'], 0x1234)
        # Clipping during YUV->RGB conversion must not hide a damaged chroma plane.
        first_x = int((20 + .5 * 1880 / 32) * 2)
        raw[width * height + 85 * width + (first_x // 2) * 2] = 0
        with self.assertRaisesRegex(ValueError, 'NV12 marker'):
            frames.decode_frame(raw, width, height, 'nv12')

    def test_nv12_rejects_partial_or_odd_geometry(self):
        with self.assertRaisesRegex(ValueError, 'expected'):
            frames.decode_frame(bytes(1920 * 1080 * 3 // 2 - 1), 1920, 1080, 'nv12')
        with self.assertRaisesRegex(ValueError, 'even'):
            frames.decode_frame(b'', 1919, 1080, 'nv12')

    def test_primary_patches_expose_channel_permutation(self):
        raw = image([0xa5123483] * 3)
        for channel, x in enumerate((240, 720, 1200)):
            offset = (800 * 1920 + x) * 3
            raw[offset + channel] = 255
        frames.check_colors(raw, 1920, 1080, 'rgb24')
        # A black/white barcode cannot reveal RGB24 accidentally emitted as BGR.
        offset = (800 * 1920 + 240) * 3
        raw[offset:offset + 3] = bytes([0, 0, 255])
        self.assertEqual(frames.decode_frame(raw)['id'], 0x1234)
        with self.assertRaisesRegex(ValueError, 'primary colour'):
            frames.check_colors(raw, 1920, 1080, 'rgb24')
