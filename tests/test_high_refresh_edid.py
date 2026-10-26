"""The experimental RTK derivative adds fixed high refresh without changing HDR/audio."""
from pathlib import Path
import unittest

from test_edge_audio_edid import data_blocks


ROOT = Path(__file__).resolve().parents[1]


class HighRefreshEdidTest(unittest.TestCase):
    def test_high_refresh_preserves_existing_video_audio_hdr_and_vrr(self):
        original = (ROOT / 'board/edid/rtk-uhd-hdr.bin').read_bytes()
        candidate = (ROOT / 'board/edid/rtk-uhd-hdr-1080p120.bin').read_bytes()
        self.assertEqual(candidate[:8], bytes.fromhex('00ffffffffffff00'))
        self.assertEqual(len(candidate), 128 * (1 + candidate[126]))
        self.assertTrue(all(sum(candidate[o:o + 128]) % 256 == 0 for o in (0, 128)))
        before, after = data_blocks(original), data_blocks(candidate)
        before_vics = next(data for tag, data in before if tag == 2)
        after_vics = next(data for tag, data in after if tag == 2)
        self.assertEqual(set(after_vics) - set(before_vics), {63, 64})
        self.assertEqual(len(before_vics), len(after_vics))
        # Capability-map bit positions are tied to the original SVD order.
        for old, new in zip(before_vics, after_vics):
            if old:
                self.assertEqual(new, old)
        self.assertEqual([block for block in before if block[0] != 2],
                         [block for block in after if block[0] != 2])
        self.assertEqual(original[:108], candidate[:108])
        self.assertEqual(original[108:114] + original[115:127],
                         candidate[108:114] + candidate[115:127])
        self.assertEqual(original[128 + original[130]:255], candidate[128 + candidate[130]:255])
        ranges = [candidate[o:o + 18] for o in range(54, 126, 18)
                  if candidate[o:o + 5] == bytes.fromhex('000000fd00')]
        self.assertEqual(len(ranges), 1)
        self.assertGreaterEqual(ranges[0][6], 120)
        self.assertGreaterEqual(ranges[0][8], 135)  # 1125 lines * 120 Hz.


if __name__ == '__main__':
    unittest.main()
