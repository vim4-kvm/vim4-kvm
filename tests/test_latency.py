"""Keep stalls, calibrated clocks and frame-ID epochs visible in latency reports."""
import importlib.util
import json
from pathlib import Path
import tempfile
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


class WindowAndClockTests(unittest.TestCase):
    def setUp(self):
        def stats(timestamp, count):
            return dict(timestamp=timestamp, ssrc=1, framesDecoded=count, bytesReceived=count * 1000,
                        framesDropped=0, packetsLost=0, freezeCount=0, keyFramesDecoded=1)
        self.history = [stats(0, 0), stats(120000, 7200),
                        stats(1680000, 100800), stats(1800000, 108000)]
        self.source, frames, timeline = [], [], []
        for epoch in (0, 1680000):
            for frame_id, offset in ((1, 0), (2, 16)):
                at = epoch + offset
                self.source.append(dict(id=frame_id, sourceMs=at, drawEndMs=at + 1))
                frames.append(dict(id=frame_id, readStartMs=at + 61, observedMs=at + 63,
                                   presentationMs=at + 60, expectedDisplayMs=at + 62,
                                   clockOffsetMs=20, clockUncertaintyMs=1))
                timeline.append(dict(presentationMs=at + 60, callbackMs=at + 61,
                                     presentedFrames=epoch // 16 + frame_id))
        self.receiver = dict(before=self.history[0], after=self.history[-1],
                             statsHistory=self.history, startedMs=0, endedMs=1800000,
                             frames=frames, timeline=timeline, invalidMarkers=0,
                             clockMapping='per-sample-wall-offset', clockDiscontinuities=0)

    def summarize(self, **options):
        with tempfile.TemporaryDirectory() as directory:
            source, receiver = Path(directory) / 'source.jsonl', Path(directory) / 'receiver.json'
            source.write_text(''.join(json.dumps(frame) + '\n' for frame in self.source))
            receiver.write_text(json.dumps(self.receiver))
            return latency.summarize(source, receiver, **options)

    def test_soak_windows_do_not_match_wrapped_ids_to_the_wrong_epoch(self):
        with self.assertRaisesRegex(ValueError, 'wrapped'):
            self.summarize()
        for start in (0, 1680):
            result = self.summarize(window_start=start, window_seconds=120)
            self.assertEqual(result['presentationMs']['median'], 60)
            self.assertEqual(result['decodedFPS'], 60)
        with self.assertRaisesRegex(ValueError, 'boundaries'):
            self.summarize(window_start=300, window_seconds=120)

    def test_calibrated_offsets_do_not_relax_clock_uncertainty_or_jump_checks(self):
        self.assertEqual(self.summarize(window_seconds=120)['clockUncertaintyMs']['max'], 1)
        self.receiver['frames'][0]['clockUncertaintyMs'] = 3
        with self.assertRaisesRegex(ValueError, 'calibration'):
            self.summarize(window_seconds=120)
        self.receiver['frames'][0]['clockUncertaintyMs'] = 1
        self.receiver['clockDiscontinuities'] = 1
        with self.assertRaisesRegex(ValueError, 'calibration'):
            self.summarize(window_seconds=120)
        del self.receiver['clockMapping']
        with self.assertRaisesRegex(ValueError, 'mapping exceeded'):
            self.summarize(window_seconds=120)
