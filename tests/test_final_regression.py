"""Audio source cleanup must run even when strict continuity rejects playback."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('final_regression', ROOT / 'packaging/kernel-edge/final-regression.py')
regression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regression)


class FixtureSnapshotTest(unittest.TestCase):
    def test_gpu_dependency_and_e02_guard_are_explicit_snapshot_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, audio = root / 'video', root / 'audio'
            video.mkdir()
            audio.mkdir()
            for name in ('fixture.py', 'modes.jsonl', 'configure', 'watch-source-events',
                         'display-list', 'run-browser.py', 'run-tool.py', 'smoke-4k.py'):
                (video / name).touch()
            (video / 'raw-modes.py').write_text("        emit({'switch':mode,\n")
            (video / 'browser-modes.mjs').write_text(
                "if(codec==='h265')assert(selected.every(id=>modes[id].width%8===0&&modes[id].height%8===0),'HEVC geometry unsafe');")
            (video / 'gpu-check.py').write_text('/var/tmp/vim4-gpu-devfreq-20261021/gles-load')
            for name in ('browser-rates.py', 'browser-audio.mjs', 'run-browser.py', 'tone', 'mac-audio'):
                (audio / name).touch()
            helpers = root / 'build/kernel-edge'
            (helpers / 'gpu-ir-deploy').mkdir(parents=True)
            (helpers / 'gpu-ir-deploy/latency-source').touch()
            (helpers / 'usb-edge-transfer.img').touch()
            workload = root / 'gles-load'
            workload.write_bytes(b'qualified workload')
            for enabled in (False, True):
                destination = root / str(enabled)
                args = SimpleNamespace(destination=destination, video_assets=video, audio_assets=audio,
                                       logs=root / 'logs', sample_modes=None, wifi_scan=False,
                                       gpu_load=workload, hevc_visible_sizes=enabled)
                with patch.object(regression, 'ROOT', root), \
                        patch.object(regression.subprocess, 'run', side_effect=AssertionError('not offline')):
                    regression.prepare(args)
                guard = (destination / 'video/browser-modes.mjs').read_text()
                self.assertIn('%2===0' if enabled else '%8===0', guard)
                self.assertEqual((destination / 'video/gpu-check.py').read_text(),
                                 regression.REMOTE + '/gles-load')
                receipt = json.loads((destination / 'fixtures.json').read_text())
                self.assertEqual(receipt['sha256']['gles-load'], regression.sha(workload))
                self.assertEqual(receipt['hevc_visible_sizes'], enabled)
                self.assertEqual(len(json.loads((destination / 'regression.json').read_text())), 9)
            workload.unlink()
            self.assertEqual((destination / 'gles-load').read_bytes(), b'qualified workload')


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
