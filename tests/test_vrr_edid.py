"""VRR policy preserves fixed modes and never invents local sink capability."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'board'))
from vim4vrr import AMD, FORUM, Range, capabilities, cta_blocks, rewrite, select_range


class VrrEdidTest(unittest.TestCase):
    def setUp(self):
        self.rtk = (ROOT / 'board/edid/rtk-uhd-hdr.bin').read_bytes()
        self.receiver = Range(48, 120)

    def test_original_rtk_is_freesync_only_and_local_needs_forum_sink(self):
        self.assertEqual(capabilities(self.rtk), {'amd-freesync': Range(40, 61)})
        with self.assertRaisesRegex(ValueError, 'does not advertise'):
            select_range(self.receiver, Range(40, 120), 'hdmi-forum', self.rtk)
        with self.assertRaisesRegex(ValueError, 'requires HDMI Forum'):
            select_range(self.receiver, Range(40, 120), 'amd-freesync', self.rtk)

    def test_rtk_experiment_is_reproducible_without_changing_fixed_timings(self):
        from board.vim4edid import rtk_extended
        candidate = (ROOT / 'board/edid/rtk-uhd-hdr-1080p120.bin').read_bytes()
        self.assertEqual(candidate, rtk_extended(self.rtk))
        self.assertEqual(candidate, rewrite(candidate, 'hdmi-forum', Range(48, 120)))
        self.assertEqual(capabilities(candidate), {'hdmi-forum': Range(48, 120)})

    def test_remote_range_is_independent_of_output_but_local_intersects(self):
        self.assertEqual(select_range(self.receiver, Range(40, 100), 'hdmi-forum'), Range(48, 100))
        sink = rewrite(self.rtk, 'hdmi-forum', Range(40, 100))
        self.assertEqual(select_range(self.receiver, Range(40, 120), 'hdmi-forum', sink), Range(48, 100))
        with self.assertRaises(ValueError):
            select_range(Range(20, 30), Range(20, 30), 'hdmi-forum', sink)

    def test_rewriting_preserves_audio_hdr_video_dtds_and_base_edid(self):
        candidate = rewrite(self.rtk, 'hdmi-forum', Range(48, 120))
        self.assertEqual(candidate[:128], self.rtk[:128])
        before, old_end = cta_blocks(self.rtk[128:])
        after, new_end = cta_blocks(candidate[128:])
        unrelated = lambda blocks: [(tag, payload) for tag, payload in blocks
                                   if tag != 3 or payload[:3] not in (AMD, FORUM)]
        self.assertEqual(unrelated(before), unrelated(after))
        self.assertEqual(self.rtk[128 + old_end:255].rstrip(b'\0'),
                         candidate[128 + new_end:255].rstrip(b'\0'))
        self.assertEqual(capabilities(candidate), {'hdmi-forum': Range(48, 120)})
        self.assertEqual(rewrite(candidate, 'hdmi-forum', Range(48, 120)), candidate)

    def test_protocol_fields_and_ten_bit_maximum_round_trip(self):
        candidate = rewrite(self.rtk, 'hdmi-forum', Range(40, 1023))
        self.assertEqual(capabilities(candidate), {'hdmi-forum': Range(40, 1023)})
        candidate = rewrite(candidate, 'amd-freesync', Range(48, 120))
        self.assertEqual(capabilities(candidate), {'amd-freesync': Range(48, 120)})
        for protocol, limits in [('hdmi-forum', Range(49, 120)), ('amd-freesync', Range(40, 256))]:
            with self.assertRaises(ValueError):
                rewrite(self.rtk, protocol, limits)

    def test_malformed_and_full_cta_do_not_drop_capabilities(self):
        broken = bytearray(self.rtk)
        broken[130] = 5
        broken[255] = -sum(broken[128:255]) % 256
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            capabilities(bytes(broken))
        full = bytearray(self.rtk)
        full[128 + self.rtk[130]:255] = bytes([1]) * (127 - self.rtk[130])
        full[255] = -sum(full[128:255]) % 256
        # Preserve an unknown vendor block so removing AMD cannot free space.
        blocks, end = cta_blocks(full[128:])
        for index, (tag, payload) in enumerate(blocks):
            if tag == 3 and payload[:3] == AMD:
                blocks[index] = (3, b'\x12\x34\x56' + payload[3:])
        full[132:128 + end] = b''.join(bytes([(tag << 5) | len(p)]) + p for tag, p in blocks)
        full[255] = -sum(full[128:255]) % 256
        with self.assertRaisesRegex(ValueError, 'no room'):
            rewrite(bytes(full), 'hdmi-forum', Range(48, 120))

    def test_reserved_forum_values_never_generate_or_qualify_a_sink(self):
        for maximum in (49, 60, 99):
            with self.assertRaisesRegex(ValueError, 'reserved'):
                rewrite(self.rtk, 'hdmi-forum', Range(48, maximum))
        valid = rewrite(self.rtk, 'hdmi-forum', Range(48, 100))
        self.assertEqual(capabilities(valid), {'hdmi-forum': Range(48, 100)})
        offset = valid.index(FORUM)
        for minimum, maximum, error in [(48, 60, 'reserved'), (49, 120, 'minimum'),
                                        (48, 0, 'depends on the video mode')]:
            broken = bytearray(valid)
            broken[offset + 8:offset + 10] = bytes([minimum, maximum])
            broken[255] = -sum(broken[128:255]) % 256
            with self.assertRaisesRegex(ValueError, error):
                select_range(self.receiver, self.receiver, 'hdmi-forum', bytes(broken))

    def test_cli_never_loads_edid_and_rejects_missing_local_monitor(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'candidate.bin'
            command = [sys.executable, str(ROOT / 'tools/vrr-edid.py'),
                       str(ROOT / 'board/edid/rtk-uhd-hdr.bin'), '--receiver', '48', '120',
                       '--request', '48', '120', '--protocol', 'hdmi-forum', '--output', str(output)]
            result = subprocess.run(command + ['--mode', 'local'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            subprocess.run(command + ['--mode', 'remote'], capture_output=True, check=True)
            self.assertEqual(capabilities(output.read_bytes()), {'hdmi-forum': Range(48, 120)})
            self.assertNotEqual(subprocess.run(command + ['--mode', 'remote'], capture_output=True).returncode, 0)

    def test_cli_rejects_unencodable_intersection_without_widening_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'candidate.bin'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/vrr-edid.py'),
                str(ROOT / 'board/edid/rtk-uhd-hdr.bin'), '--receiver', '48', '120',
                '--request', '48', '60', '--protocol', 'hdmi-forum', '--mode', 'remote',
                '--output', str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('reserved', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
