"""Offline transaction ordering: no real SSH, locks, installation or reboot."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('final_window', ROOT / 'packaging/kernel-edge/final-window.py')
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)


class FinalWindowTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.logs = self.root / 'logs'
        self.logs.mkdir()
        self.plan = [dict(id=name, argv=['offline-fixture', name], timeout=30)
                     for name in sorted(window.REQUIRED_CHECKS)]
        release = '7.3.0-vim4kvm-uhd1+'
        (self.bundle / 'Image').write_bytes(b'Linux version ' + release.encode() + b' fixture')
        (self.bundle / 'vim4.dtb').write_bytes(b'\xd0\x0d\xfe\xed' + bytes(32))
        for name in ('one-kvm', 'vim4-manager'):
            (self.bundle / name).write_bytes(b'\x7fELF\x02\x01' + bytes(12) + bytes([183, 0]))
        contents = b'fixture kernel module'
        with tarfile.open(self.bundle / 'modules.tar.gz', 'w:gz') as archive:
            member = tarfile.TarInfo(release + '/kernel/test.ko')
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))
        modules = {'kernel/test.ko': hashlib.sha256(contents).hexdigest()}
        artifacts = {name: window.sha(self.bundle / name) for name in ('Image', 'vim4.dtb', 'modules.tar.gz')}
        report = dict(source='a' * 40, release=release, artifacts=artifacts, modules=modules, module_count=1)
        (self.bundle / 'manifest.json').write_text(json.dumps(report))
        (self.bundle / 'runtime-proof.json').write_text(json.dumps(dict(
            release=release, image_sha256=artifacts['Image'], module_sha256=modules)))
        self.proof = dict(commits=dict(kernel='a' * 40, onekvm='b' * 40, manager='c' * 40),
                          sha256={p.name: window.sha(p) for p in self.bundle.iterdir()}, checks=self.plan)
        self.write_proof()
        self.args = SimpleNamespace(host='vim4', bundle=self.bundle, logs=self.logs,
                                    backup='/var/backups/vim4-offline-test')

    def write_proof(self):
        (self.bundle / 'deployment.json').write_text(json.dumps(self.proof))

    def test_dry_run_has_no_process_or_network_calls(self):
        args = ['final-window.py', 'window', '--bundle', str(self.bundle), '--backup', self.args.backup,
                '--logs', str(self.logs), '--dry-run']
        with patch.object(sys, 'argv', args), patch.object(window.subprocess, 'run') as run, \
                patch.object(window.subprocess, 'check_output') as read, contextlib.redirect_stdout(io.StringIO()):
            window.main()
        run.assert_not_called()
        read.assert_not_called()

    def test_missing_regression_category_is_rejected_before_contacting_board(self):
        self.proof['checks'].pop()
        self.write_proof()
        with patch.object(window, 'run') as process, self.assertRaisesRegex(AssertionError, 'Every regression'):
            window.Window(self.args).deploy()
        process.assert_not_called()

    def test_corrupt_bundle_is_rejected_before_contacting_board(self):
        self.proof['sha256'] = {'Image': '0' * 64}
        (self.bundle / 'Image').write_bytes(b'corrupt')
        self.write_proof()
        with patch.object(window, 'run') as process, self.assertRaises(AssertionError):
            window.Window(self.args).deploy()
        process.assert_not_called()

    def test_different_registration_proof_is_rejected_before_contacting_board(self):
        path = self.bundle / 'runtime-proof.json'
        proof = json.loads(path.read_text())
        proof['module_sha256']['kernel/test.ko'] = '0' * 64
        path.write_text(json.dumps(proof))
        self.proof['sha256'][path.name] = window.sha(path)
        self.write_proof()
        with patch.object(window, 'run') as process, self.assertRaisesRegex(AssertionError, 'Registration proof'):
            window.Window(self.args).deploy()
        process.assert_not_called()

    def transaction(self, failure):
        events = []
        controller = window.Window(self.args)

        def remote(command, **options):
            if 'sudo dmesg;' in command:
                events.append('diagnostic-board')
            if 'stdout' in options:
                options['stdout'].write(b'backup contents')

        def action(name):
            events.append(name)
            if name == failure:
                raise RuntimeError('injected ' + name)
            if failure == 'after-first-regression' and name == 'verify' and self.plan[0]['id'] in events:
                raise RuntimeError('injected post-regression health failure')

        def regression(item):
            events.append(item['id'])
            if item['id'] == failure:
                raise RuntimeError('injected regression')

        digest = hashlib.sha256(b'backup contents').hexdigest()
        def process(*args, **options):
            if str(args[0]).endswith('/mac-hdr-mode'):
                events.append('diagnostic-source')

        with patch.object(controller, 'remote', side_effect=remote), \
                patch.object(controller, 'action', side_effect=action), \
                patch.object(controller, 'reboot', side_effect=lambda: events.append('reboot')), \
                patch.object(controller, 'regression', side_effect=regression), \
                patch.object(window, 'run', side_effect=process), patch.object(window.subprocess, 'check_output', return_value=digest):
            if failure and failure not in window.REQUIRED_CHECKS - window.CRITICAL_CHECKS:
                with self.assertRaises(RuntimeError):
                    controller.deploy()
            else:
                controller.deploy()
        return events

    def test_success_retains_candidate_only_after_every_regression(self):
        events = self.transaction(None)
        self.assertEqual(events[:5], ['save', 'install', 'reboot', 'verify', 'health'])
        self.assertEqual(events[5:-2], [value for item in self.plan for value in (item['id'], 'verify')])
        self.assertEqual(events[-2], 'health')
        self.assertEqual(events[-1], 'finalize')
        self.assertNotIn('restore', events)

    def test_partial_install_and_failed_health_restore_and_verify_baseline(self):
        for failure in ('install', 'verify', 'h264'):
            with self.subTest(failure=failure):
                # Each run requires a new Mac backup location.
                self.args.logs = self.root / failure
                self.args.logs.mkdir()
                events = self.transaction(failure)
                self.assertEqual(events[-3:], ['restore', 'reboot', 'verify-restore'])
                self.assertNotIn('finalize', events)

    def test_audio_and_other_noncritical_failures_are_recorded_and_retained(self):
        for failure in ('audio', 'gpu', 'manager', 'media', '4k60'):
            with self.subTest(failure=failure):
                self.args.logs = self.root / failure
                self.args.logs.mkdir()
                events = self.transaction(failure)
                self.assertEqual(events[-1], 'finalize')
                self.assertNotIn('restore', events)
                results = json.loads((self.args.logs / 'regression-results.json').read_text())
                self.assertFalse(next(item for item in results if item['id'] == failure)['passed'])
                self.assertEqual(len(results), len(window.REQUIRED_CHECKS))

    def test_post_regression_failure_preserves_passed_result_before_rollback(self):
        events = self.transaction('after-first-regression')
        self.assertEqual(events[-3:], ['restore', 'reboot', 'verify-restore'])
        results = json.loads((self.args.logs / 'regression-results.json').read_text())
        self.assertEqual(results, [dict(id=self.plan[0]['id'], passed=True)])
        self.assertLess(events.index('diagnostic-board'), events.index('diagnostic-source'))
        self.assertLess(events.index('diagnostic-source'), events.index('restore'))

    def test_pstore_readback_failure_rolls_back_after_extra_reboot(self):
        self.proof['verify_pstore'] = True
        self.write_proof()
        events = self.transaction('pstore-verify')
        index = events.index('pstore-mark')
        self.assertEqual(events[index:index + 4], ['pstore-mark', 'reboot', 'verify', 'pstore-verify'])
        self.assertEqual(events[-3:], ['restore', 'reboot', 'verify-restore'])
        self.assertNotIn('finalize', events)
