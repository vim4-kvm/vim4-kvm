"""A healthy active span must not hide stopped playback or missed callbacks."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'latency', Path(__file__).resolve().parents[1] / 'tools/latency-summary.py')
latency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(latency)


class CadenceTests(unittest.TestCase):
    def test_stopped_stream_keeps_silent_tail_in_whole_window_rate(self):
        result = latency.cadence({
            'startedMs': 0, 'endedMs': 1000,
            'timeline': [
                {'presentationMs': 10, 'callbackMs': 11, 'presentedFrames': 1},
                {'presentationMs': 30, 'callbackMs': 31, 'presentedFrames': 2},
            ],
        })
        self.assertEqual(result['activePresentedFPS'], 50)
        self.assertEqual(result['presentedFPS'], 1)
        self.assertEqual(result['trailingNoCallbackMs'], 969)
        self.assertEqual(result['maxNoCallbackMs'], 969)

    def test_no_frames_does_not_disappear_from_summary(self):
        result = latency.cadence({'startedMs': 10, 'endedMs': 2010, 'timeline': []})
        self.assertEqual(result['maxNoCallbackMs'], 2000)
        self.assertEqual(result['presentedFPS'], 0)

    def test_missed_callbacks_are_not_called_dropped_video_frames(self):
        result = latency.cadence({
            'startedMs': 0, 'endedMs': 200,
            'timeline': [
                {'presentationMs': 10, 'callbackMs': 11, 'presentedFrames': 20},
                {'presentationMs': 110, 'callbackMs': 115, 'presentedFrames': 26},
            ],
        })
        self.assertEqual(result['missedCallbacks'], 5)
        self.assertEqual(result['activePresentedFPS'], 60)
        self.assertEqual(result['intervalsOverMs']['50'], 1)

    def test_restarted_presentation_counter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reset'):
            latency.cadence({
                'startedMs': 0, 'endedMs': 200,
                'timeline': [
                    {'presentationMs': 10, 'callbackMs': 11, 'presentedFrames': 20},
                    {'presentationMs': 30, 'callbackMs': 31, 'presentedFrames': 1},
                ],
            })
