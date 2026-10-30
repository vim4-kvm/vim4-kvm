import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'npu_validate', Path(__file__).resolve().parents[1] / 'tools/npu-validate.py')
NPU = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NPU)


class QualificationTests(unittest.TestCase):
    def baseline(self):
        return dict(model='model', input='input', probe='probe', samples=[1., 2., 3.],
                    outputs={'iteration-0000-output-0.f32': {'sha256': 'abc', 'bytes': 4}})

    def test_full_output_difference_fails_before_performance(self):
        baseline = self.baseline()
        candidate = copy.deepcopy(baseline)
        candidate['outputs']['iteration-0000-output-0.f32']['sha256'] = 'def'
        candidate['samples'] = [.1, .2, .3]
        with self.assertRaisesRegex(ValueError, 'byte equality'):
            NPU.compare(baseline, candidate)

    def test_performance_boundary_and_tail_statistics(self):
        baseline = self.baseline()
        candidate = copy.deepcopy(baseline)
        candidate['samples'] = [x * 1.05 for x in baseline['samples']]
        self.assertTrue(NPU.compare(baseline, candidate)['passed'])
        candidate['samples'][-1] += .01
        self.assertFalse(NPU.compare(baseline, candidate)['passed'])
        self.assertEqual(NPU.statistics([1., 2., 100.])['p99'], 100.)

    def test_invalid_timing_rejected(self):
        for samples in ([], [float('nan')], [0.], [-1.]):
            with self.assertRaises(ValueError):
                NPU.statistics(samples)

    def test_timeout_terminates_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(subprocess.TimeoutExpired):
                NPU.bounded_probe([sys.executable, '-c', 'import time; time.sleep(60)'],
                                  Path(directory), .05)

    def test_failed_probe_is_not_qualified(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'probe failed'):
                NPU.bounded_probe([sys.executable, '-c', 'raise SystemExit(7)'],
                                  Path(directory), 1)
