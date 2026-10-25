import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('passthrough_monitor', Path(__file__).resolve().parents[1] / 'tools/passthrough-monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class PassthroughHealthTest(unittest.TestCase):
    def test_short_ready_gap_is_not_a_black_screen_and_stalls_are_counted_once(self):
        health = monitor.ScanoutHealth()
        for now, ready, frame in [(0, True, 10), (1, False, 70), (2, True, 130), (3, True, 130), (4, True, 130), (5, True, 130)]:
            health.observe(now, True, True, ready, frame)
        self.assertEqual((health.ready_losses, health.stalls), (0, 1))
        health.observe(6, True, True, True, 1)
        health.observe(7, True, True, True, 61)
        self.assertEqual(health.stalls, 1)

    def test_absent_input_or_disabled_video_does_not_count_as_unexpected_stall(self):
        health = monitor.ScanoutHealth()
        for now in range(10):
            health.observe(now, True, False, False, 0)
        for now in range(10, 20):
            health.observe(now, False, True, False, 0)
        self.assertEqual((health.ready_losses, health.stalls), (0, 0))
        for now in range(20, 24):
            health.observe(now, True, True, False, now)
        self.assertEqual(health.ready_losses, 1)
