import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/vdec-window.py'
SPEC = importlib.util.spec_from_file_location('vdec_window', SOURCE)
window = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(window)


class DecoderWindowTests(unittest.TestCase):
    def test_baseline_requires_each_service_active(self):
        with patch.object(window, 'run', side_effect=['active\n', 'inactive\n']) as run, \
                self.assertRaises(ValueError):
            window.require_services()
        self.assertEqual([call.args[-1] for call in run.call_args_list], ['one-kvm', 'vim4-manager'])

    def test_every_action_defaults_to_offline_without_ssh(self):
        for action in window.ACTIONS:
            with self.subTest(action=action), patch.object(sys, 'argv', [str(SOURCE), action]), \
                    patch.object(window.subprocess, 'run') as run, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                window.main()
                self.assertTrue(json.loads(output.getvalue())['offline'])
                run.assert_not_called()

    def test_execute_requires_both_onsite_flag_and_manifest(self):
        for flags in ([], ['--at-board'], ['--manifest', '/nonexistent']):
            with self.subTest(flags=flags), \
                    patch.object(sys, 'argv', [str(SOURCE), 'wave', '--execute', *flags]), \
                    patch.object(window.subprocess, 'run') as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                window.main()
            run.assert_not_called()

    def test_baseline_manifest_cannot_run_candidate_window(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'manifest.json'
            manifest.write_text(json.dumps({'release': '7.3.0-vim4kvm-uhd1+'}))
            with patch.object(sys, 'argv', [str(SOURCE), 'probe', '--execute', '--at-board',
                                           '--manifest', str(manifest)]), \
                    patch.object(window.subprocess, 'run') as run, self.assertRaises(ValueError):
                window.main()
            run.assert_not_called()

    def test_timeout_is_not_retried(self):
        with patch.object(window.subprocess, 'run', side_effect=subprocess.TimeoutExpired('test', 10)) as run, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            window.run('test', timeout=10)
        self.assertEqual(run.call_count, 1)

    def test_no_codec_command_before_baseline_boot_files_are_armed(self):
        args = SimpleNamespace(action='power', build_id='candidate')
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_baseline_files', side_effect=ValueError('not armed')), \
                patch.object(window, 'run') as run, self.assertRaises(ValueError):
            window.board_window(args)
        run.assert_not_called()

    def test_timeout_quarantines_without_unload_reload_or_service_restart(self):
        args = SimpleNamespace(action='power', build_id='candidate', fixtures='/fixtures')
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window.Path, 'glob', return_value=[]), \
                patch.object(window.Path, 'write_text') as marker, \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_baseline_files'), \
                patch.object(window, 'faulted', return_value=False), \
                patch.object(window, 'video_node', return_value='/dev/video99'), \
                patch.object(window.subprocess, 'run') as service, \
                patch.object(window, 'run', side_effect=['', '', subprocess.TimeoutExpired('v4l2-ctl', 8)]) as run, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            service.return_value.returncode = 0
            window.board_window(args)
        marker.assert_called_once()
        self.assertEqual([call.args[:2] for call in run.call_args_list],
                         [('systemctl', 'stop'), ('modprobe', 'aml-vdec-drv'), ('v4l2-ctl', '-d')])


if __name__ == '__main__':
    unittest.main()
