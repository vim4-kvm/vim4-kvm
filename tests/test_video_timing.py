"""Prevent misleading timing summaries from mixed sessions or unmatched frames."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'timing', Path(__file__).resolve().parents[1] / 'tools/video-timing-summary.py')
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


def frame(pts, age=12, size=2000, sent_size=2000, viewers=1):
    return (f'timing read pts_ns={pts} capture_to_copy_ms={age} '
            f'copy_to_read_ms=0.1 bytes={size} key=true\n'
            f'timing send pts_ns={pts} send_ms=2 bytes={sent_size} viewers={viewers}\n')


class TimingTests(unittest.TestCase):
    capture = ('delivery_to_dequeue_ms=0.04 sequence=360\n'
               'delivery_to_dequeue_ms=0.06 sequence=362\n')

    def test_warmup_unknown_age_and_multiple_viewers(self):
        application = (frame(0, age=99) + frame(6_000_000_000, age=-1)
                       + frame(7_000_000_000, age=10)
                       + frame(8_000_000_000, age=90, viewers=2))
        result = timing.summarize(application, self.capture)
        self.assertEqual(result['source_to_copy_ms']['median'], 10)
        self.assertEqual(result['source_to_copy_ms']['count'], 1)
        self.assertEqual(result['send_key_ms']['count'], 2)
        self.assertEqual(result['delivery_sequence_gaps'], 1)

    def test_restarted_sessions_and_wrong_frame_pairing_are_rejected(self):
        good = frame(6_000_000_000)
        for application, capture in (
            (good + frame(0), self.capture),
            (good, self.capture * 2),
            (frame(6_000_000_000, sent_size=1), self.capture),
            (frame(6_000_000_000, viewers=2), self.capture),
        ):
            with self.subTest(application=application, capture=capture):
                with self.assertRaises(ValueError):
                    timing.summarize(application, capture)


if __name__ == '__main__':
    unittest.main()
