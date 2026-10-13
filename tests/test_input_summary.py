"""Reject incomplete input evidence instead of reporting misleading latency."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'input_summary', Path(__file__).resolve().parents[1] / 'tools/input-summary.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class InputSummaryTests(unittest.TestCase):
    def setUp(self):
        self.browser = [
            dict(kind='phase', name='hold', at=0),
            dict(kind='report', at=10, clockOffset=0, bytes=[1, 0, 0, 79, 0, 0, 0, 0, 0]),
            dict(kind='report', at=1000, clockOffset=0, bytes=[1, 0, 0, 0, 0, 0, 0, 0, 0]),
            dict(kind='phase', name='done', at=1600),
        ]
        self.host = [
            dict(kind='ready', receivedMs=0),
            dict(kind='keydown', receivedMs=14, repeat=False),
            dict(kind='keydown', receivedMs=514, repeat=True),
            dict(kind='keyup', receivedMs=1004, repeat=False),
        ]

    def test_target_repeat_is_not_extra_browser_input(self):
        result = summary.summarize(self.browser, self.host)['hold']
        self.assertEqual(result['down']['count'], 1)
        self.assertEqual(result['down']['median'], 4)
        self.assertEqual(result['repeat_delay_ms'], 500)
        self.assertEqual(result['repeated_events'], 1)

    def test_missing_release_and_repeat_after_release_fail(self):
        for host in (self.host[:-1], self.host + [
                dict(kind='keydown', receivedMs=1100, repeat=True)]):
            with self.subTest(host=host), self.assertRaises(ValueError):
                summary.summarize(self.browser, host)

    def test_bad_clock_and_incomplete_run_fail(self):
        drifted = copy.deepcopy(self.browser)
        drifted[1]['clockOffset'] = 3
        for browser in (drifted, self.browser[:-1]):
            with self.subTest(browser=browser), self.assertRaises(ValueError):
                summary.summarize(browser, self.host)


if __name__ == '__main__':
    unittest.main()
