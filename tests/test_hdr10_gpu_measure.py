"""Cadence statistics retain stalls and never turn missing samples into zero."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'hdr10_measure', Path(__file__).resolve().parents[1] / 'packaging/hdr10/measure-gpu.py')
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class GPUCadenceTest(unittest.TestCase):
    def test_stall_is_retained_in_tail_and_throughput(self):
        timestamps = [0]
        for interval in [16_000_000] * 98 + [50_000_000, 80_000_000]:
            timestamps.append(timestamps[-1] + interval)
        result = measure.metrics(timestamps)
        self.assertEqual(result['p99_ms'], 50)
        self.assertEqual(result['max_ms'], 80)
        self.assertAlmostEqual(result['fps'], 100 / 1.698)

    def test_missing_or_invalid_sequence_is_rejected(self):
        for timestamps in ([], [1], [1, 1], [2, 1], [1, 3, 2]):
            with self.subTest(timestamps=timestamps), self.assertRaises(ValueError):
                measure.metrics(timestamps)
