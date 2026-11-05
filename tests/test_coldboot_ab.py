import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'packaging/kernel'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ab = load('coldboot_ab', 'coldboot-ab.py')
collector = load('coldboot_collector', 'coldboot-collect.py')


class ColdbootTests(unittest.TestCase):
    def test_collector_preserves_parameters_config_hashes_and_missing_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {'sys/module/aml_vdec_drv/parameters/enable_t7': 'N\n',
                     'proc/sys/kernel/random/boot_id': 'test-boot\n',
                     'etc/modprobe.d/decoder.conf': 'options aml_vdec_drv enable_t7=0\n'}
            for name, value in files.items():
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                collector.snapshot(root)
            rows = {item['path']: item for item in map(json.loads, output.getvalue().splitlines())}
            self.assertEqual(rows['/sys/module/aml_vdec_drv/parameters/enable_t7']['value'], 'N\n')
            self.assertIn('sha256', rows['/etc/modprobe.d/decoder.conf'])
            self.assertIn('error', rows['/proc/cmdline'])
            self.assertFalse(rows['/run/modprobe.d']['exists'])

    def test_collector_timeout_keeps_partial_output_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            def timed_out(command, **kwargs):
                kwargs['stdout'].write('{"path":"/proc/cmdline","value":"partial"}\n')
                raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            with patch.object(collector.subprocess, 'run', side_effect=timed_out), contextlib.redirect_stdout(io.StringIO()):
                collector.capture(Path(temporary), 'initial')
            self.assertEqual(json.loads((Path(temporary)/'initial.status.json').read_text())['status'], 'timeout')
            self.assertIn('partial', (Path(temporary)/'initial.jsonl').read_text())

    def test_default_cli_only_validates_without_acquiring_ticket(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary)/'config.json'
            config.write_text('{}')
            with patch.object(ab, 'preflight', return_value=({}, {})), \
                    patch.object(ab.window, 'require_board') as lease, \
                    patch.object(ab.Batch, 'execute') as execute, \
                    patch('sys.argv', ['coldboot-ab', str(config)]), contextlib.redirect_stdout(io.StringIO()):
                ab.main()
            lease.assert_not_called()
            execute.assert_not_called()

    def test_fatal_sample_restores_once_and_never_starts_later_samples(self):
        self.run_batch(fail=True)

    def test_complete_batch_uses_exact_twenty_alternating_samples(self):
        self.run_batch(fail=False)

    def run_batch(self, fail):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)/'evidence'
            proof = dict(files={}, release='formal')
            plans = dict(A=dict(build_id='a'), B=dict(build_id='b'))
            batch = ab.Batch(dict(A=dict(sha256='a'), B=dict(sha256='b')), proof, plans,
                             directory, 'unused', 'unused')
            queue = Mock()
            queue.read.return_value = dict(started=ab.time.time(), seconds=3000)
            stream = Mock()
            calls = []
            def sample(group, number, uart):
                calls.append(group+number)
                if fail:
                    raise RuntimeError('kernel warning')
            with patch.object(ab.window, 'require_board', return_value=(queue, 'ticket')), \
                    patch.object(ab.window, 'continuous_uart', return_value=contextlib.nullcontext(stream)), \
                    patch.object(ab.window, 'ssh_python', return_value='mountinfo'), \
                    patch.object(ab.window, 'stage_bundle'), patch.object(ab, 'checked_file'), \
                    patch.object(batch, 'baseline'), patch.object(batch, 'video'), \
                    patch.object(batch, 'firmware'), patch.object(batch, 'sample', side_effect=sample), \
                    patch.object(batch, 'restore') as restore:
                if fail:
                    with self.assertRaisesRegex(RuntimeError, 'kernel warning'):
                        batch.execute()
                else:
                    batch.execute()
            self.assertEqual(calls, ['A1'] if fail else [g+n for g,n in ab.schedule()])
            self.assertEqual(len(calls), 1 if fail else 20)
            restore.assert_called_once_with(stream)
            self.assertEqual(queue.sampling.call_args_list[-1].args, ('ticket', False))

    def test_slot_expiration_is_not_swallowed_as_missing_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            batch = ab.Batch({}, {}, dict(A=dict(release='trial', build_id='id')),
                             Path(temporary), 'unused', 'unused')
            stream = Mock()
            stream.events = SimpleNamespace(linux_started=1)
            stream.cold_reset.return_value = False
            with patch.object(ab.window, 'boot'), \
                    patch.object(ab.window, 'identity', return_value=dict(release='trial', build_id='id')), \
                    patch.object(ab.window, 'verify_candidate_dt'), \
                    patch.object(batch, 'snapshots', side_effect=ab.SlotExpired('slot expired')):
                with self.assertRaises(ab.SlotExpired):
                    batch.sample('A', '1', stream)
            self.assertEqual(batch.results[0]['status'], 'invalid')

    def test_cold_reset_consumes_one_sample_and_recovers_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            batch = ab.Batch({}, {}, dict(B=dict(release='trial', build_id='id')),
                             Path(temporary), 'unused', 'unused')
            stream = Mock()
            stream.events = SimpleNamespace(linux_started=10, reset_at=20)
            stream.cold_reset.return_value = True
            with patch.object(ab.window, 'boot', side_effect=RuntimeError('cold reset')) as boot, \
                    patch.object(batch, 'automatic_recovery') as recover:
                batch.sample('B', '1', stream)
            boot.assert_called_once()
            recover.assert_called_once_with(stream)
            self.assertEqual(batch.results[0]['status'], 'cold-reset')
            self.assertEqual(len(batch.results), 1)

    def test_automatic_recovery_failure_propagates_instead_of_resuming(self):
        with tempfile.TemporaryDirectory() as temporary:
            batch = ab.Batch({}, {}, dict(A={}), Path(temporary), 'unused', 'unused')
            stream = Mock()
            stream.events = SimpleNamespace(linux_started=10, reset_at=20)
            stream.cold_reset.return_value = True
            with patch.object(ab.window, 'boot', side_effect=RuntimeError('cold reset')), \
                    patch.object(batch, 'automatic_recovery', side_effect=TimeoutError('recovery failed')):
                with self.assertRaisesRegex(TimeoutError, 'recovery failed'):
                    batch.sample('A', '1', stream)

    def test_short_ticket_cannot_open_uart_or_touch_board(self):
        batch = ab.Batch({}, {}, {}, Path('/unused'), 'unused', 'unused')
        queue = Mock()
        queue.read.return_value = dict(started=ab.time.time(), seconds=120)
        with patch.object(ab.window, 'require_board', return_value=(queue, 'ticket')), \
                patch.object(ab.window, 'continuous_uart') as uart:
            with self.assertRaisesRegex(RuntimeError, 'fresh approved'):
                batch.execute()
        uart.assert_not_called()
        queue.sampling.assert_not_called()

    def test_partial_firmware_creation_is_retained_on_ssh_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = dict(firmware=dict(source='/source', relative='brcm/test.bin', sha256='a'*64))
            batch = ab.Batch(config, {}, dict(A=dict(release='a'), B=dict(release='b')),
                             Path(temporary), 'unused', 'unused')
            error = subprocess.TimeoutExpired('ssh', 30, output=b'{"created":"/owned/a"}\n')
            with patch.object(ab.subprocess, 'run', side_effect=error):
                with self.assertRaises(subprocess.TimeoutExpired):
                    batch.firmware()
            self.assertEqual(batch.created_firmware, ['/owned/a'])
            self.assertEqual(json.loads((Path(temporary)/'owned-firmware.json').read_text()), ['/owned/a'])


if __name__ == '__main__':
    unittest.main()
