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

    def test_known_panicking_candidate_is_blocked_before_ssh_but_allows_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'manifest.json'
            for source in window.FAILED_SOURCES:
                for release in ('7.3.0-vim4kvm-vdec3+', '7.3.0-vim4kvm-vdec4+'):
                    proof = {'release': release, 'source': source}
                    manifest.write_text(json.dumps(proof))
                    for action in set(window.ACTIONS) - {'arm-baseline', 'verify-baseline'}:
                        with self.subTest(source=source, release=release, action=action), \
                                patch.object(sys, 'argv', [str(SOURCE), action, '--execute', '--at-board',
                                                           '--manifest', str(manifest)]), \
                                patch.object(window.subprocess, 'run') as run, self.assertRaises(ValueError):
                            window.main()
                        run.assert_not_called()
                    for action in ('arm-baseline', 'verify-baseline'):
                        window.require_candidate(action, proof)

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
                patch.object(window, 'begin_stage', return_value={}), \
                patch.object(window, 'finish_stage'), \
                patch.object(window, 'power_cycle', side_effect=subprocess.TimeoutExpired('power_test', 8)), \
                patch.object(window, 'faulted', return_value=False), \
                patch.object(window, 'video_node', return_value='/dev/video99'), \
                patch.object(window.subprocess, 'run') as service, \
                patch.object(window, 'run') as run, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            service.return_value.returncode = 0
            window.board_window(args)
        marker.assert_called_once()
        self.assertEqual([call.args[:2] for call in run.call_args_list],
                         [('systemctl', 'stop'), ('modprobe', 'aml-vdec-drv')])

    def test_unsuspended_close_preserves_recovery_marker_without_unloading(self):
        args = SimpleNamespace(action='power', build_id='candidate', fixtures='/fixtures')
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            (device / 'power').mkdir()
            (device / 'power/runtime_status').write_text('active\n')
            fault = device / 'faulted'
            fault.write_text('0\n')
            with patch.object(window.os, 'geteuid', return_value=0), \
                    patch.object(window.Path, 'exists', return_value=False), \
                    patch.object(window.Path, 'glob', autospec=True,
                                 side_effect=lambda path, pattern: [fault] if pattern == '*/faulted' else []), \
                    patch.object(window.Path, 'write_text') as marker, \
                    patch.object(window, 'build_id', return_value='candidate'), \
                    patch.object(window, 'require_baseline_files'), \
                    patch.object(window, 'begin_stage', return_value={}), \
                    patch.object(window, 'finish_stage'), \
                    patch.object(window, 'power_cycle', side_effect=lambda: window.require_suspended(device)), \
                    patch.object(window, 'faulted', return_value=False), \
                    patch.object(window, 'video_node', return_value='/dev/video99'), \
                    patch.object(window.subprocess, 'run') as service, \
                    patch.object(window, 'run') as run, \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                service.return_value.returncode = 1
                window.board_window(args)
            marker.assert_called_once()
            self.assertEqual([call.args[:2] for call in run.call_args_list],
                             [('systemctl', 'stop'), ('modprobe', 'aml-vdec-drv')])

    def test_stage_receipts_require_order_and_reject_incomplete_or_repeated_window(self):
        read_text = Path.read_text
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window.Path, 'read_text', autospec=True,
                             side_effect=lambda path: 'boot-test' if str(path).startswith('/proc/')
                             else read_text(path)):
            path = Path(directory) / 'stages.json'
            args = SimpleNamespace(action='power', build_id='test')
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            args.action = 'probe'
            state = window.begin_stage(args, path)
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            window.finish_stage(state, True, path)
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            args.action = 'power'
            state = window.begin_stage(args, path)
            window.finish_stage(state, False, path)
            for action in ('probe', 'power', 'mdec', 'compliance', 'h264', 'wave'):
                args.action = action
                with self.subTest(action=action), self.assertRaises(ValueError):
                    window.begin_stage(args, path)

    def test_power_cycle_requires_verified_off_state_and_relocks_open(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            (device / 'power_test').write_text('passed=1 DOS_SW_RESET0=0x0\n')
            state = device / 'power_state'
            state.write_text('VDEC[4]=1 NIC3[39]=0 (0=on 1=off)\n')
            with patch.object(window, 't7_device', return_value=device), \
                    patch.object(window, 'run') as run, \
                    patch.object(window, 'set_power_permission') as permission, \
                    patch.object(window, 'require_suspended'), \
                    contextlib.redirect_stdout(io.StringIO()):
                window.power_cycle()
                self.assertEqual([call.args[0] for call in permission.call_args_list], [True, False])
                self.assertEqual(run.call_args_list[-1].kwargs['timeout'], 8)
                state.write_text('VDEC[4]=0 NIC3[39]=0 (0=on 1=off)\n')
                with self.assertRaises(RuntimeError):
                    window.power_cycle()

    def test_compliance_requires_mdec_receipt_even_after_power_passed(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window.Path, 'read_text', return_value='boot-test'):
            path = Path(directory) / 'stages.json'
            path.touch()
            identity = {'boot': 'boot-test', 'build': 'test'}
            state = {'identity': identity, 'passed': ['probe', 'power']}
            with patch.object(window.json, 'loads', return_value=state):
                args = SimpleNamespace(action='compliance', build_id='test')
                with self.assertRaisesRegex(ValueError, 'Required previous stage: mdec'):
                    window.begin_stage(args, path)

    def test_mdec_cycle_blocks_open_on_read_or_power_off_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            result = device / 'mdec_test'
            state = device / 'power_state'
            for passed, off in ((False, True), (True, False), (True, True)):
                result.write_text(f'passed={int(passed)} MDEC_PIC_DC_CTRL=0x0\n')
                state.write_text(f'VDEC[4]={int(off)} NIC3[39]=0\n')
                with self.subTest(passed=passed, off=off), \
                        patch.object(window, 'power_cycle') as power, \
                        patch.object(window, 't7_device', return_value=device), \
                        patch.object(window, 'run') as run, \
                        patch.object(window, 'set_power_permission') as permission, \
                        patch.object(window, 'require_suspended'), \
                        contextlib.redirect_stdout(io.StringIO()):
                    if passed and off:
                        window.mdec_cycle()
                    else:
                        with self.assertRaises(RuntimeError):
                            window.mdec_cycle()
                    power.assert_called_once()
                    self.assertIn('mdec_test', run.call_args.args[-1])
                    self.assertEqual(run.call_args.kwargs['timeout'], 8)
                    self.assertEqual([c.args[0] for c in permission.call_args_list],
                                     [True, False] if passed and off else [True])


if __name__ == '__main__':
    unittest.main()
