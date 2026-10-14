"""Check the hardware LUT boundaries without writing to a running receiver."""
from pathlib import Path
import subprocess
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
