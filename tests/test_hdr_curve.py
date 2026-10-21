"""Check the hardware LUT boundaries without writing to a running receiver."""
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/hdr-curve.sh'


class HDRCurveTests(unittest.TestCase):
    def tables(self, white, peak):
        return subprocess.run(['sh', str(TOOL), 'tables', str(white), str(peak)],
                              capture_output=True, text=True)

    def test_hardware_tables_at_supported_boundaries(self):
        for white, peak in ((160, 161), (160, 10000), (203, 1000), (1000, 1001), (1000, 10000)):
            with self.subTest(white=white, peak=peak):
                result = self.tables(white, peak)
                self.assertEqual(result.returncode, 0, result.stderr)
                gain, encoding = ([int(n) for n in line.split(',')]
                                  for line in result.stdout.splitlines())
                for table in (gain, encoding):
                    self.assertEqual(len(table), 149)
                    self.assertTrue(all(0 <= n <= 4095 for n in table))
                self.assertTrue(all(a >= b for a, b in zip(gain, gain[1:])))
                self.assertTrue(all(a <= b for a, b in zip(encoding, encoding[1:])))
                self.assertEqual(encoding[0], 0)
                self.assertEqual(encoding[-1], 4095)

    def test_invalid_parameters_never_emit_a_partial_table(self):
        for white, peak in (('159', '1000'), ('1001', '2000'), ('203', '203'),
                            ('203', '10001'), ('', '1000'), ('203:1', '1000'),
                            ('203', '1:000'), ('2e2', '1000'), ('0203', '1000')):
            with self.subTest(white=white, peak=peak):
                result = self.tables(white, peak)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')

    def test_apply_uses_atomic_edge_pair_and_preserves_legacy_reload(self):
        # Replace only the sysfs boundary; execute the actual shell generator.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                '/sys/module/aml_media/parameters/oo_y_lut_hdr_sdr': root / 'gain',
                '/sys/module/aml_media/parameters/oe_y_lut_sdr': root / 'encoding',
                '/sys/class/vdin/vdin0/attr': root / 'reload',
                '/sys/bus/platform/devices/ff000000.video-capture/hdr_curve': root / 'edge',
            }
            script = TOOL.read_text()
            for source, target in paths.items():
                script = script.replace(source, str(target))
                target.write_text('unchanged')
            candidate = root / 'curve.sh'
            candidate.write_text(script)
            def apply(white, peak):
                return subprocess.run(['sh', str(candidate), 'apply', str(white), str(peak)],
                                      capture_output=True, text=True)
            expected = self.tables(203, 1000).stdout
            self.assertEqual(apply(203, 1000).returncode, 0)
            self.assertEqual((root / 'edge').read_text(), expected)
            for name in ('gain', 'encoding', 'reload'):
                self.assertEqual((root / name).read_text(), 'unchanged')
            self.assertEqual(apply(159, 1000).returncode, 2)
            self.assertEqual((root / 'edge').read_text(), expected)
            (root / 'edge').unlink()
            self.assertEqual(apply(203, 1000).returncode, 0)
            gain, encoding = expected.splitlines()
            self.assertEqual((root / 'gain').read_text(), gain + '\n')
            self.assertEqual((root / 'encoding').read_text(), encoding + '\n')
            self.assertEqual((root / 'reload').read_text(), 'reload_hdr\n')
