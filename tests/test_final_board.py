"""A source/EDID transition is transient; a persistently broken link is not."""
import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    'final_board', Path(__file__).resolve().parents[1] / 'packaging/kernel-edge/final-board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class StatusRecoveryTest(unittest.TestCase):
    def test_edid_restore_may_relock_after_multiple_status_reads(self):
        path = Mock()
        path.read_text.side_effect = ['source_5v: 1\nlink_ready: 0\n'] * 2 + [
            'source_5v: 1\nlink_ready: 1\n']
        with patch.object(board.time, 'monotonic', side_effect=[0, .1, .2]), \
                patch.object(board.time, 'sleep'):
            value = board.wait_for_status(path, ['source_5v: 1', 'link_ready: 1'])
        self.assertIn('link_ready: 1', value)
        self.assertEqual(path.read_text.call_count, 3)

    def test_persistent_loss_or_capture_fault_expires_with_last_evidence(self):
        for status, required in [('link_ready: 0', ['link_ready: 1']),
                                 ('faulted: 1\nstream_error: 0', ['faulted: 0', 'stream_error: 0'])]:
            with self.subTest(status=status):
                path = Mock()
                path.read_text.return_value = status
                with patch.object(board.time, 'monotonic', side_effect=[0, .1, 1.1]), \
                        patch.object(board.time, 'sleep'), \
                        self.assertRaisesRegex(RuntimeError, 'did not recover within 1s') as error:
                    board.wait_for_status(path, required, timeout=1)
                self.assertIn(status, str(error.exception))


class ModuleRecoveryTest(unittest.TestCase):
    def test_restore_survives_wedged_service_manager(self):
        with tempfile.TemporaryDirectory() as temporary:
            backup = Path(temporary)
            (backup / 'COMPLETE').touch()
            (backup / 'state.json').write_text(json.dumps({'files': {}, 'missing': []}))
            instance = object.__new__(board.Board)
            instance.backup = backup
            calls = []

            def execute(command, **kwargs):
                calls.append(command)
                return Mock(returncode=0)

            def launch(command, **kwargs):
                calls.append(command)
                for stream in ('stdin', 'stdout', 'stderr'):
                    self.assertEqual(kwargs[stream], board.subprocess.DEVNULL)
                process = Mock()
                if command[0] == 'systemctl':
                    process.wait.side_effect = board.subprocess.TimeoutExpired(command, 10)
                else:
                    self.assertEqual(command[:2], ['sync', '-f'])
                    process.wait.return_value = 0
                return process

            with patch.object(board.subprocess, 'run', side_effect=execute), \
                    patch.object(board.subprocess, 'Popen', side_effect=launch), \
                    patch.object(board.Path, 'unlink'), \
                    patch.object(board.shutil, 'chown'), \
                    patch.object(instance, 'restore_modules') as modules, \
                    patch.object(board.os, 'sync') as sync:
                instance.restore()
            self.assertEqual(sum(command[0] == 'tar' for command in calls), 1)
            modules.assert_called_once()
            sync.assert_not_called()
            self.assertTrue((backup / 'application-restore-pending').exists())
            self.assertIn(['systemctl', 'daemon-reload'], calls)

    def test_recovery_script_survives_payload_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, backup = root / 'payload', root / 'backup'
            payload.mkdir()
            backup.mkdir()
            (payload / 'final-board.py').write_text('print("RECOVERY_EXECUTED")\n')
            for name in ('deployment.json', 'manifest.json'):
                (payload / name).write_text('{}')
            instance = object.__new__(board.Board)
            instance.payload, instance.backup = payload, backup
            instance.prepare_rollback()
            board.shutil.rmtree(payload)
            result = board.subprocess.check_output([str(backup / 'rollback.sh'), 'verify'], text=True)
            self.assertIn('RECOVERY_EXECUTED', result)
            # Recovery already syncs its local filesystems; an extra global sync
            # in the wrapper would bring the stalled NAS back into the path.
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            sync = bin_dir / 'sync'
            sync.write_text('#!/bin/sh\nexit 91\n')
            sync.chmod(0o755)
            env = dict(board.os.environ, PATH=str(bin_dir) + ':' + board.os.environ['PATH'])
            result = board.subprocess.check_output([str(backup / 'rollback.sh'), 'restore'], env=env, text=True)
            self.assertIn('RECOVERY_EXECUTED', result)

    def test_same_release_partial_install_restores_original_directory(self):
        for phase in ('before-rename', 'after-rename', 'after-install'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                modules, backup = root / 'modules', root / 'backup'
                modules.mkdir()
                backup.mkdir()
                (modules / 'baseline.ko').write_bytes(b'original BTF')
                (backup / 'state.json').write_text(json.dumps({'modules': board.tree(modules)}))
                if phase != 'before-rename':
                    modules.rename(backup / 'original-modules')
                if phase == 'after-install':
                    modules.mkdir()
                    (modules / 'candidate.ko').write_bytes(b'new BTF')
                instance = object.__new__(board.Board)
                instance.baseline = {'release': board.RELEASE}
                instance.backup = backup
                with patch.object(board, 'MODULES', modules):
                    instance.restore_modules()
                self.assertEqual((modules / 'baseline.ko').read_bytes(), b'original BTF')
                self.assertFalse((modules / 'candidate.ko').exists())
                if phase == 'after-install':
                    self.assertEqual((backup / 'candidate-modules/candidate.ko').read_bytes(), b'new BTF')


class StopFailureRecoveryTest(unittest.TestCase):
    def test_timed_out_stop_is_killed_without_another_blocking_wait(self):
        process = Mock()
        process.wait.side_effect = board.subprocess.TimeoutExpired('systemctl', 10)
        with patch.object(board.subprocess, 'Popen', return_value=process):
            self.assertFalse(board.bounded_command(['systemctl', 'stop', 'vim4-manager']))
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=10)
        with patch.object(board.subprocess, 'Popen', side_effect=OSError('cannot start systemctl')):
            self.assertFalse(board.bounded_command(['systemctl', 'stop', 'vim4-manager']))

    def test_stop_failures_cannot_prevent_boot_files_modules_and_sync(self):
        for stops in ((False, True), (True, False), (False, False), (True, True)):
            with self.subTest(stops=stops), tempfile.TemporaryDirectory() as temporary:
                backup = Path(temporary)
                (backup / 'COMPLETE').touch()
                target = backup / 'Image'
                target.write_bytes(b'candidate')
                (backup / 'state.json').write_text(json.dumps({'files': {str(target): 'hash'}, 'missing': []}))
                instance = object.__new__(board.Board)
                instance.backup = backup
                instance.restore_modules = Mock()
                instance.restore_application = Mock(side_effect=lambda:
                    (backup / 'application-restore-pending').unlink())
                order = []

                def restore_files(args, **kwargs):
                    target.write_bytes(b'baseline')
                    order.append('files')

                def synced(state):
                    self.assertEqual(target.read_bytes(), b'baseline')
                    instance.restore_modules.assert_called_once_with()
                    order.append('sync')

                with patch.object(board, 'bounded_command', side_effect=[*stops, False]), \
                        patch.object(board.subprocess, 'run', side_effect=restore_files), \
                        patch.object(board, 'sync_restored_files', side_effect=synced):
                    instance.restore()
                self.assertEqual(order, ['files', 'sync'])
                self.assertEqual(target.read_bytes(), b'baseline')
                self.assertEqual(instance.restore_application.call_count, int(all(stops)))
                self.assertEqual((backup / 'application-restore-pending').exists(), not all(stops))

    def test_deferred_database_restore_cannot_pass_baseline_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            instance = object.__new__(board.Board)
            instance.backup = Path(temporary)
            (instance.backup / 'application-restore-pending').touch()
            with self.assertRaisesRegex(AssertionError, 'Application restore pending'):
                instance.verify_restore()

    def test_sync_timeout_is_not_reported_as_durable_restore(self):
        with patch.object(board, 'bounded_command', return_value=False), self.assertRaisesRegex(RuntimeError, 'sync failed'):
            board.sync_restored_files({'files': {'/boot/edge/Image': 'hash'}})

    def test_daemon_reload_is_attempted_after_sync_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            instance = object.__new__(board.Board)
            instance.backup = Path(temporary)
            (instance.backup / 'COMPLETE').touch()
            (instance.backup / 'state.json').write_text(json.dumps({'files': {}, 'missing': []}))
            with patch.object(board, 'bounded_command', return_value=False) as command, \
                    patch.object(board.subprocess, 'run'), \
                    patch.object(instance, 'restore_modules') as modules, \
                    patch.object(board, 'sync_restored_files', side_effect=RuntimeError('sync failed')), \
                    self.assertRaisesRegex(RuntimeError, 'sync failed'):
                instance.restore()
            modules.assert_called_once_with()
            self.assertEqual(command.call_args.args[0], ['systemctl', 'daemon-reload'])
            self.assertTrue((instance.backup / 'application-restore-pending').exists())


if __name__ == '__main__':
    unittest.main()
