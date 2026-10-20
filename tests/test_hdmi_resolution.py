"""A nominal UHD frame must not hide a 1080p downscale/upscale."""
import importlib.util
from pathlib import Path
import unittest

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


@unittest.skipIf(Image is None, 'Pillow is required for offline spatial-detail checks')
class ResolutionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tools/hdmi-resolution-check.py'
        spec = importlib.util.spec_from_file_location('resolution_check', path)
        cls.check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.check)
        cls.reference = Image.new('L', (3840, 2160), 64)
        draw = ImageDraw.Draw(cls.reference)
        for row in range(2):
            for column, pitch in enumerate((1, 2, 4, 8)):
                x, y = 128 + column * 896, 256 + row * 896
                for line in range(512 if row else 640):
                    colour = 255 if (line // pitch) % 2 else 0
                    if row:
                        draw.line((x, y + line, x + 639, y + line), fill=colour)
                    else:
                        draw.line((x + line, y, x + line, y + 511), fill=colour)

    def test_same_geometry_with_1080p_detail_is_rejected(self):
        reduced = self.reference.resize((1920, 1080), Image.Resampling.BOX)
        upscaled = reduced.resize((3840, 2160), Image.Resampling.BILINEAR)
        self.assertFalse(self.check.compare(self.reference, upscaled)['native_single_pixel_detail'])

    def test_native_detail_survives_brightness_and_range_changes(self):
        limited_range = self.reference.point(lambda p: round(16 + p * 219 / 255))
        result = self.check.compare(self.reference, limited_range)
        self.assertTrue(result['native_single_pixel_detail'])
        self.assertTrue(all(tile['passed'] for tile in result['tiles']))

    def test_css_screenshot_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unscaled'):
            self.check.compare(self.reference, self.reference.resize((1687, 949)))
