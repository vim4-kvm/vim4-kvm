import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'tools/encoder-vbv-summary.py'
SPEC = importlib.util.spec_from_file_location('vbv_summary', PATH)
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


class VbvSummaryTests(unittest.TestCase):
    def test_peak_includes_last_complete_window(self):
        self.assertAlmostEqual(SUMMARY.peak_mbps([1, 1, 4, 5], 2, fps=2), 72 / 1e6)
        with self.assertRaises(ValueError):
            SUMMARY.peak_mbps([100], 2)

    def test_fifo_accumulates_burst_and_drains_during_idle(self):
        rows = [dict(pts_ns=0, bytes=200), dict(pts_ns=100_000_000, bytes=100),
                dict(pts_ns=1_000_000_000, bytes=100)]
        delays = SUMMARY.fifo_tail_ms(rows, 8000)
        for actual, expected in zip(delays, [200, 200, 100]):
            self.assertAlmostEqual(actual, expected)

    def test_fifo_media_origin_does_not_change_delay(self):
        rows = [dict(pts_ns=i * 20_000_000, bytes=100) for i in range(10)]
        shifted = [dict(row, pts_ns=row['pts_ns'] + 1_000_000_000) for row in rows]
        for first, second in zip(SUMMARY.fifo_tail_ms(rows, 16000), SUMMARY.fifo_tail_ms(shifted, 16000)):
            self.assertAlmostEqual(first, second)
