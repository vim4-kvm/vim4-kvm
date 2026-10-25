import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('hdmi_color_check', Path(__file__).resolve().parents[1] / 'tools/hdmi-color-check.py')
color = importlib.util.module_from_spec(spec)
spec.loader.exec_module(color)


class HdmiColorCheckTest(unittest.TestCase):
    def test_sdr_reference_obeys_wire_range_and_chroma_order(self):
        self.assertEqual(color.reference([64, 512, 512], False), [0, 0, 0])
        self.assertEqual(color.reference([940, 512, 512], False), [255, 255, 255])
        neutral = color.reference([464, 512, 512], False)
        self.assertAlmostEqual(neutral[0], 116.438356, places=5)
        self.assertEqual(neutral, [neutral[0]] * 3)
        red = color.reference([252, 408, 960], False)
        self.assertGreater(red[0], 254)
        self.assertLess(red[1], 1)
        self.assertLess(red[2], 1)
        swapped = color.reference([252, 960, 408], False)
        self.assertGreater(swapped[2], 250)
        self.assertLess(swapped[0], 20)

    def test_hdr_reference_uses_pq_and_configured_white_not_sdr_gamma(self):
        self.assertEqual(color.reference([64, 512, 512], True), [0, 0, 0])
        corrected = color.reference([571, 512, 512], True)
        vendor = color.reference([571, 512, 512], True, 400)
        self.assertTrue(all(250 < value < 254 for value in corrected))
        self.assertTrue(all(185 < value < 189 for value in vendor))
        with self.assertRaises(ValueError):
            color.reference([1024, 512, 512], True)
