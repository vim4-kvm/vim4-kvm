"""Check the hardware LUT boundaries without writing to a running receiver."""
from pathlib import Path
from bisect import bisect_left
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/hdr-curve.sh'


class HDRCurveTests(unittest.TestCase):
    def tables(self, white, peak, action='tables'):
        return subprocess.run(['sh', str(TOOL), action, str(white), str(peak)],
                              capture_output=True, text=True)

    def test_hardware_tables_at_supported_boundaries(self):
        for action in ('tables', 'tables-edge'):
            for white, peak in ((160, 161), (160, 10000), (203, 1000), (1000, 1001), (1000, 10000)):
                with self.subTest(white=white, peak=peak, action=action):
                    result = self.tables(white, peak, action)
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
                '/sys/class/vdin/vdin1/attr': root / 'secondary',
                '/sys/module/aml_media/parameters/vdin0_native_hdr': root / 'native',
                '/sys/module/aml_media/parameters/vdin_oo_y_lut_hdr_sdr': root / 'capture-gain',
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
            expected = self.tables(203, 1000, 'tables-edge').stdout
            self.assertEqual(apply(203, 1000).returncode, 0)
            self.assertEqual((root / 'edge').read_text(), expected)
            for name in ('gain', 'encoding', 'reload'):
                self.assertEqual((root / name).read_text(), 'unchanged')
            self.assertEqual(apply(159, 1000).returncode, 2)
            self.assertEqual((root / 'edge').read_text(), expected)
            (root / 'edge').unlink()
            self.assertEqual(apply(203, 1000).returncode, 0)
            gain, encoding = self.tables(203, 1000).stdout.splitlines()
            self.assertEqual((root / 'gain').read_text(), gain + '\n')
            self.assertEqual((root / 'encoding').read_text(), encoding + '\n')
            self.assertEqual((root / 'reload').read_text(), 'reload_hdr\n')
            self.assertEqual((root / 'capture-gain').read_text(), gain + '\n')
            self.assertEqual((root / 'secondary').read_text(), 'unchanged')
            (root / 'native').write_text('Y\n')
            self.assertEqual(apply(203, 1000).returncode, 0)
            self.assertEqual((root / 'secondary').read_text(), 'reload_hdr\n')

    def test_edge_curve_preserves_midtones_and_distinguishes_highlights(self):
        positions = ([0] + [2 ** (i + 3) for i in range(1, 8)]
                     + [2 ** (j - 2) * i + 2 ** j for j in range(11, 20) for i in range(4)]
                     + [2 ** (j - 3) * i + 2 ** j for j in range(20, 31) for i in range(8)]
                     + [2 ** 27 * i + 2 ** 31 for i in range(16)] + [2 ** 32 - 1])
        def interpolate(values, position):
            index = max(1, min(148, bisect_left(positions, position)))
            fraction = (position - positions[index - 1]) / (positions[index] - positions[index - 1])
            return values[index - 1] + fraction * (values[index] - values[index - 1])
        def output(peak, nits):
            gain, encoding = ([int(n) for n in line.split(',')]
                              for line in self.tables(203, peak, 'tables-edge').stdout.splitlines())
            level = nits / 10000 * 2 ** 32
            linear = level * interpolate(gain, level) / 64
            return round(16 + 219 * interpolate(encoding, linear) / 4095)
        self.assertGreaterEqual(output(1000, 600) - output(1000, 400), 2)
        self.assertGreaterEqual(output(1000, 1000) - output(1000, 600), 2)
        self.assertGreater(output(1000, 600), output(10000, 600))
        legacy = [int(n) for n in self.tables(203, 1000).stdout.splitlines()[0].split(',')]
        edge = [int(n) for n in self.tables(203, 1000, 'tables-edge').stdout.splitlines()[0].split(',')]
        for nits in [1, 5, 25, 50, 100, 150]:
            self.assertEqual(interpolate(legacy, nits / 10000 * 2 ** 32),
                             interpolate(edge, nits / 10000 * 2 ** 32))
