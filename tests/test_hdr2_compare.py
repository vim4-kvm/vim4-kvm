import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'packaging/hdr2-pq/compare_frames.py'
spec = importlib.util.spec_from_file_location('hdr2_compare', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Hdr2CompareTest(unittest.TestCase):
    def test_self_noise_and_top_region_keep_visible_chroma_rows(self):
        original = bytes(range(12))
        changed = bytearray(original)
        changed[0] += 20
        changed[8] += 20
        full = module.compare(original, changed, 2, 4, 12, 12,
                              vendor_format='nv12')[0]
        cropped = module.compare(original, changed, 2, 4, 12, 12,
                                 exclude_top=2, vendor_format='nv12')[0]
        self.assertEqual(full['Y']['max'], 20)
        self.assertEqual(full['U']['max'], 20)
        self.assertTrue(all(c['max'] == 0 for c in cropped.values()))
        changed[10] += 3
        cropped = module.compare(original, changed, 2, 4, 12, 12,
                                 exclude_top=2, vendor_format='nv12')[0]
        self.assertEqual(cropped['U']['max'], 3)
        for top in (-2, 1, 4):
            with self.assertRaises(ValueError):
                module.compare(original, changed, 2, 4, 12, 12, exclude_top=top)

    def test_chroma_order_and_tail_padding_across_frames(self):
        vendor = bytes([16, 32, 64, 235, 201, 90, 255, 255,
                        20, 40, 80, 200, 202, 91, 0, 0])
        nv12 = bytes([16, 32, 64, 235, 90, 201,
                      20, 40, 80, 200, 91, 202])
        reports = module.compare(vendor, nv12, 2, 2, 8, 6)
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(c['max'] == 0 for frame in reports for c in frame.values()))
        changed = bytearray(nv12)
        changed[6] += 7
        reports = module.compare(vendor, changed, 2, 2, 8, 6)
        self.assertEqual(reports[1]['Y']['max'], 7)
        self.assertEqual(reports[0]['Y']['max'], 0)

    def test_partial_or_missing_frames_are_rejected(self):
        for vendor, candidate in [(b'1234567', b'123456'), (b'12345678', b''),
                                  (b'', b'')]:
            with self.assertRaises(ValueError):
                module.compare(vendor, candidate, 2, 2, 8, 6)
