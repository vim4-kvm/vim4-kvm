"""Audio source cleanup must run even when strict continuity rejects playback."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('final_regression', ROOT / 'packaging/kernel-edge/final-regression.py')
regression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regression)


class AudioCleanupTest(unittest.TestCase):
    def check_failure_cleanup(self, fail_restore):
        events = []
        tone = Mock()
        tone.terminate.side_effect = lambda: events.append('stop-tone')

        def run(argv, **options):
            if len(argv) == 2:
                return subprocess.CompletedProcess(argv, 0)
            if argv[0] == 'node':
                events.append('measure')
                raise subprocess.CalledProcessError(1, argv)
            if argv[0] == 'ssh':
                events.append('confirm-rate')
                if fail_restore:
                    raise subprocess.TimeoutExpired(argv, 45)
            else:
                events.append('set-rate')

        expected = subprocess.TimeoutExpired if fail_restore else subprocess.CalledProcessError
        with patch.object(regression.subprocess, 'Popen', return_value=tone), \
                patch.object(regression.subprocess, 'run', side_effect=run), self.assertRaises(expected):
            regression.audio_continuity(Path('/offline/audio'), {})
        self.assertEqual(events, ['set-rate', 'measure', 'set-rate', 'confirm-rate', 'stop-tone'])
        tone.wait.assert_called_once_with(timeout=10)

    def test_failed_playback_restores_source_before_stopping_tone(self):
        self.check_failure_cleanup(False)

    def test_failed_rate_recovery_still_stops_our_source(self):
        self.check_failure_cleanup(True)

    def test_edid_device_reappearance_precedes_opening_tone(self):
        events = []
        probes = iter((7, 0))

        def execute(argv, **options):
            code = next(probes) if len(argv) == 2 else 0
            if len(argv) == 2:
                events.append(('device', code))
            return subprocess.CompletedProcess(argv, code)

        def open_tone(*args):
            events.append('open-tone')
            return Mock()

        with patch.object(regression.subprocess, 'Popen', side_effect=open_tone), \
                patch.object(regression.subprocess, 'run', side_effect=execute), \
                patch.object(regression.time, 'sleep'):
            regression.audio_continuity(Path('/offline/audio'), {})
        self.assertEqual(events, [('device', 7), ('device', 0), 'open-tone'])

    def test_missing_source_does_not_open_a_tone_or_change_rate(self):
        missing = subprocess.CompletedProcess(['mac-audio'], 7)
        with patch.object(regression.subprocess, 'Popen') as tone, \
                patch.object(regression.subprocess, 'run', return_value=missing) as run, \
                patch.object(regression.time, 'monotonic', side_effect=[0, 31]), \
                self.assertRaisesRegex(RuntimeError, 'did not reappear'):
            regression.audio_continuity(Path('/offline/audio'), {})
        tone.assert_not_called()
        self.assertEqual(run.call_count, 1)
