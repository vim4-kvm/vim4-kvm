"""The shared RTK profile preserves fixed high refresh and unrelated HDR/audio capabilities."""
from pathlib import Path
import unittest

from test_edge_audio_edid import data_blocks


ROOT = Path(__file__).resolve().parents[1]


class HighRefreshEdidTest(unittest.TestCase):
    def test_high_refresh_preserves_existing_video_audio_hdr_and_dtds(self):
        original = (ROOT / 'board/edid/rtk-uhd-hdr.bin').read_bytes()
        candidate = (ROOT / 'board/edid/rtk-uhd-hdr-1080p120.bin').read_bytes()
        self.assertEqual(candidate[:8], bytes.fromhex('00ffffffffffff00'))
        self.assertEqual(len(candidate), 128 * (1 + candidate[126]))
        self.assertTrue(all(sum(candidate[o:o + 128]) % 256 == 0 for o in range(0, len(candidate), 128)))
        before, after = data_blocks(original), data_blocks(candidate)
        before_vics = next(data for tag, data in before if tag == 2)
        after_vics = next(data for tag, data in after if tag == 2)
        self.assertEqual(set(after_vics) - set(before_vics), {63, 64})
        self.assertEqual(len(before_vics), len(after_vics))
        # Capability-map bit positions are tied to the original SVD order.
        for old, new in zip(before_vics, after_vics):
            if old:
                self.assertEqual(new, old)
        def unrelated(block):
            tag, payload = block
            return tag != 2 and not (tag == 3 and payload[:3] in
                                    (bytes.fromhex('1a0000'), bytes.fromhex('d85dc4')))
        self.assertEqual([block for block in before if unrelated(block)],
                         [block for block in after if unrelated(block)])
        self.assertEqual(original[:108], candidate[:108])
        self.assertEqual(original[108:114] + original[115:116] + original[117:126],
                         candidate[108:114] + candidate[115:116] + candidate[117:126])
        self.assertEqual(original[128 + original[130]:255].rstrip(b'\0'),
                         candidate[128 + candidate[130]:255].rstrip(b'\0'))
        ranges = [candidate[o:o + 18] for o in range(54, 126, 18)
                  if candidate[o:o + 5] == bytes.fromhex('000000fd00')]
        self.assertEqual(len(ranges), 1)
        self.assertGreaterEqual(ranges[0][6], 120)
        self.assertGreaterEqual(ranges[0][8], 135)  # 1125 lines * 120 Hz.

    def test_extended_timings_fit_the_receiver_and_preserve_preferred_4k(self):
        candidate = (ROOT / 'board/edid/rtk-uhd-hdr-1080p120.bin').read_bytes()
        self.assertEqual(len(candidate), 384)
        extension = candidate[256:]
        self.assertEqual(extension[4:6], bytes((0x41, 90)))  # 2560x1080p60.
        modes = []
        for offset in (6, 24):
            timing = extension[offset:offset + 18]
            width = timing[2] | (timing[4] & 0xf0) << 4
            height = timing[5] | (timing[7] & 0xf0) << 4
            htotal = width + timing[3] + ((timing[4] & 15) << 8)
            vtotal = height + timing[6] + ((timing[7] & 15) << 8)
            clock = int.from_bytes(timing[:2], 'little') * 10000
            modes.append((width, height, round(clock / (htotal * vtotal))))
            self.assertLessEqual(clock, 600000000)
            self.assertLessEqual(clock / htotal, candidate[116] * 1000)
        self.assertEqual(modes, [(2560, 1440, 120), (3440, 1440, 60)])


if __name__ == '__main__':
    unittest.main()
