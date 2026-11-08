"""Pixel measurements must catch a shifted/truncated stream or a damaged plane."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location(
    'vdec_fixtures', Path(__file__).resolve().parents[1] / 'packaging/kernel/vdec-fixtures.py')
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)


class PixelErrorTests(unittest.TestCase):
    def test_jpeg_metadata_removal_preserves_tables_and_stuffed_scan_bytes(self):
        scan = b'\xff\xdb\x00\x04\x01\x02\xff\xda\x00\x02\xff\x00\xd8\xff\xd9'
        image = b'\xff\xd8\xff\xe0\x00\x04ab\xff\xfe\x00\x04cd' + scan
        self.assertEqual(FIXTURES.jpeg_without_leading_metadata(image * 2),
                         (b'\xff\xd8' + scan) * 2)
        with self.assertRaises(ValueError):
            FIXTURES.jpeg_without_leading_metadata(b'\xff\xd8\xff\xe0\xff\xffab')

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


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires FFmpeg/ffprobe')
class HevcHangFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        encoders = subprocess.check_output(['ffmpeg', '-hide_banner', '-encoders'],
                                           stderr=subprocess.STDOUT, text=True)
        if 'libx265' not in encoders:
            raise unittest.SkipTest('requires libx265')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.mother = cls.root / 'mother.h265'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=96x96:rate=25',
                        '-frames:v', '2', '-c:v', 'libx265', '-preset', 'ultrafast',
                        '-x265-params', 'keyint=1:pools=1:frame-threads=1:repeat-headers=1',
                        '-f', 'hevc', str(cls.mother)], check=True, capture_output=True)
        cls.data = cls.mother.read_bytes()
        cls.sections = FIXTURES.hevc_hang_inspect(cls.mother)

    def test_lt_edits_preserve_slice_bytes_and_software_pixels(self):
        reference = FIXTURES.hevc_hang_reference(self.mother, 2)
        original = [self.data[p:end] for _, p, end, kind in FIXTURES.hevc_hang_nals(self.data)
                    if kind != 33]
        for count in (0, 1, 8):
            with self.subTest(count=count):
                data = FIXTURES.hevc_hang_lt_variant(self.data, self.sections, count)
                self.assertEqual([data[p:end] for _, p, end, kind in FIXTURES.hevc_hang_nals(data)
                                  if kind != 33], original)
                clip = self.root / f'lt{count}.h265'
                clip.write_bytes(data)
                sections = FIXTURES.hevc_hang_inspect(clip)
                values = [FIXTURES.hevc_hang_fields(s) for s in sections
                          if s['kind'] == 'Sequence Parameter Set']
                self.assertTrue(values)
                self.assertTrue(all(s['long_term_ref_pics_present_flag'] == 1 and
                                    s['num_long_term_ref_pics_sps'] == count for s in values))
                self.assertEqual(FIXTURES.hevc_hang_reference(clip, 2)['frame_md5'],
                                 reference['frame_md5'])

    def test_first_au_keeps_complete_idr_without_next_pictures_prefix(self):
        first = FIXTURES.hevc_hang_first_au(self.data)
        self.assertLess(len(first), len(self.data))
        clip = self.root / 'first.h265'
        clip.write_bytes(first)
        self.assertEqual(FIXTURES.hevc_hang_reference(clip, 1)['picture_types'], ['I'])
        # The next SPS prefix belongs to the next AU even before its first VCL.
        self.assertEqual(FIXTURES.hevc_hang_first_au(first + self.data), first)

    def test_unmatched_sps_trace_fails_instead_of_reusing_wrong_offsets(self):
        _, p, end, _ = next(n for n in FIXTURES.hevc_hang_nals(self.data) if n[3] == 33)
        nal = bytearray(self.data[p:end])
        nal[3] ^= 1
        with self.assertRaisesRegex(ValueError, 'complete FFmpeg trace'):
            FIXTURES.hevc_hang_patch_sps(bytes(nal), self.sections, 1)

    def test_invalid_input_hash_is_rejected_before_creating_outputs(self):
        output = self.root / 'invalid-output'
        args = SimpleNamespace(intra=self.mother, intra_sha256='0' * 64,
                               ltr=self.mother, ltr_sha256='0' * 64, output=output)
        with self.assertRaisesRegex(ValueError, 'source SHA256'):
            FIXTURES.generate_hevc_hang(args)
        self.assertFalse(output.exists())

    def test_emulation_prevention_roundtrip_keeps_header_and_payload(self):
        rbsp = b'\x42\x01\0\0\0\1\0\0\2\0\0\3\x80'
        self.assertEqual(FIXTURES.hevc_hang_rbsp(FIXTURES.hevc_hang_escape(rbsp)), rbsp)

    def test_wpp_off_is_one_column_with_real_inter_pictures(self):
        output = self.root / 'wpp-off'
        output.mkdir()
        _, case = FIXTURES.hevc_hang_wpp_off(output)
        self.assertEqual(case['frames'], 12)
        self.assertTrue({'I', 'P', 'B'} <= set(case['picture_types']))
        self.assertEqual((case['width'], case['height']), (64, 240))
        self.assertTrue(case['sps'] and case['pps'])
        self.assertTrue(all(FIXTURES.hevc_hang_ctu_size(s) == 64 for s in case['sps']))
        self.assertTrue(all(p['entropy_coding_sync_enabled_flag'] == 0 for p in case['pps']))
