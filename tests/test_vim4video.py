"""Mainline input metadata is independent of capture's last buffer dimensions."""
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('vim4video', Path(__file__).resolve().parents[1] / 'board/vim4video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class VideoMetadataTest(unittest.TestCase):
    def timings(self, width, height, clock, hblank, vblank):
        data = bytearray(132)
        struct.pack_into('=IIIIIQIIIIII', data, 0, 0, width, height, 0, 0, clock, hblank, 0, 0, vblank, 0, 0)
        return data

    def test_measured_input_dimensions_and_fractional_rate(self):
        data = self.timings(3840, 2160, 593406593, 560, 90)
        result = video.decode_timings(data)
        self.assertEqual((result['width'], result['height']), (3840, 2160))
        self.assertAlmostEqual(result['refreshHz'], 60000 / 1001, places=6)

    def test_invalid_and_interlaced_timings_are_not_reported_as_locked(self):
        for offset, value in [(0, 1), (4, 0), (12, 1)]:
            data = self.timings(1920, 1080, 148500000, 280, 45)
            struct.pack_into('=I', data, offset, value)
            with self.assertRaises(ValueError):
                video.decode_timings(data)

    def test_invalid_edid_is_rejected_before_opening_a_device(self):
        with patch.object(video, 'capture_device') as device:
            for data in [b'', bytes(128), b'\x00\xff\xff\xff\xff\xff\xff\x00' + bytes(120)]:
                with self.assertRaises(ValueError):
                    video.set_edid(data)
            device.assert_not_called()
