"""Pixel measurements must catch a shifted/truncated stream or a damaged plane."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'vdec_fixtures', Path(__file__).resolve().parents[1] / 'packaging/kernel/vdec-fixtures.py')
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)


class PixelErrorTests(unittest.TestCase):
    def test_errors_remain_separated_by_frame_and_plane(self):
        reference = bytes([100] * 48)
        captured = bytearray(reference)
        captured[0] += 1
        captured[20] -= 8
        captured[24 + 16] += 2
        errors = FIXTURES.pixel_errors(reference, captured, 4, 4)
        self.assertEqual(errors[0]['Y']['max_absolute_error'], 1)
        self.assertEqual(errors[0]['U']['max_absolute_error'], 0)
        self.assertEqual(errors[0]['V']['max_absolute_error'], 8)
        self.assertEqual(errors[1]['U']['mean_error'], -0.5)
        self.assertIsNone(errors[1]['V']['psnr_db'])
        self.assertLess(errors[0]['V']['psnr_db'], errors[0]['Y']['psnr_db'])

    def test_truncation_cannot_be_hidden_by_zip(self):
        for reference, captured in ((b'\0' * 24, b'\0' * 23), (b'\0' * 23, b'\0' * 23)):
            with self.assertRaises(ValueError):
                FIXTURES.pixel_errors(reference, captured, 4, 4)
