"""The audio EDID adds supported LPCM without changing the validated UHD timing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'packaging/kernel-edge'


def data_blocks(edid):
    cta = edid[128:256]
    offset = 4
    blocks = []
    while offset < cta[2]:
        length = cta[offset] & 31
        blocks.append((cta[offset] >> 5, cta[offset+1:offset+1+length]))
        offset += length + 1
    if offset != cta[2]:
        raise ValueError('CTA data block extends into the detailed timing area')
    return blocks


class AudioEdidTest(unittest.TestCase):
    def test_audio_capabilities_preserve_video_and_physical_identity(self):
        original = bytes.fromhex((ROOT / 'uhd60-edid.hex').read_text())
        audio = bytes.fromhex((ROOT / 'uhd60-audio-edid.hex').read_text())
        self.assertEqual(len(audio), 256)
        self.assertTrue(all(sum(audio[i:i+128]) % 256 == 0 for i in (0, 128)))
        self.assertEqual(audio[:128], original[:128])
        self.assertEqual([b for b in data_blocks(audio) if b[0] in (2, 3)], data_blocks(original))
        blocks = dict(data_blocks(audio))
        sad = blocks[1]
        self.assertEqual(len(sad), 3)
        self.assertEqual(sad[0] >> 3, 1)  # LPCM, not a compressed audio format
        self.assertEqual((sad[0] & 7) + 1, 2)
        self.assertEqual(sad[1], 7)  # 32, 44.1 and 48 kHz only
        self.assertEqual(sad[2], 1)  # 16-bit PCM only
        self.assertEqual(blocks[4], bytes((1, 0, 0)))
        self.assertTrue(audio[131] & 0x40)  # Basic Audio agrees with the LPCM SAD

    def test_audio_is_a_subset_of_the_verified_stock_rtk_profile(self):
        verified = (ROOT.parents[1] / 'board/edid/rtk-uhd-hdr.bin').read_bytes()
        audio = bytes.fromhex((ROOT / 'uhd60-audio-edid.hex').read_text())
        requested = dict(data_blocks(audio))[1]
        advertised = dict(data_blocks(verified))[1]
        lpcm = [advertised[i:i+3] for i in range(0, len(advertised), 3)
                if advertised[i] >> 3 == 1]
        self.assertEqual(len(lpcm), 1)
        original = lpcm[0]
        self.assertLessEqual((requested[0] & 7), (original[0] & 7))
        self.assertEqual(requested[1] & original[1], requested[1])
        self.assertEqual(requested[2] & original[2], requested[2])
