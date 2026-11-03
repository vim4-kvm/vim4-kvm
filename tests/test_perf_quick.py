"""A failed benchmark must release sampling and restore the original service."""
import importlib.util
import json
import os
import re
import signal
import subprocess
import threading
from pathlib import Path
import tempfile
import unittest
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quick', ROOT / 'tools/perf-quick.py')
quick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick)


class PMCancellationTest(unittest.TestCase):
    def test_real_subprocess_wait_enters_rollback_promptly(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig), self.assertRaises(quick.PMCancelled), quick.pm_cancellation() as (_, wait):
                timer = threading.Timer(.2, os.kill, args=(os.getpid(), sig))
                timer.start()
                start = time.monotonic()
                try:
                    wait(lambda: subprocess.check_output(['/bin/sleep', '6'], timeout=8,
                                                         text=True, start_new_session=True))
                    self.fail('cancelled subprocess wait returned normally')
                finally:
                    timer.join()
                    self.assertLess(time.monotonic() - start, 2)


class PMWindowTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.args = SimpleNamespace(phase='h264', output=Path(temp.name)/'A'/'h264', schedutil=True)
        self.queue = Mock()
        self.item = dict(state='held', heavy=False, started=time.time(), seconds=1800)
        self.queue.read.return_value = self.item
        self.events = []
        self.queue.sampling.side_effect = lambda _, on: self.events.append(('sampling', on))
        self.service = 'active'
        self.hdmi = dict(signal=True, width=3840, height=2160, refreshHz=59.94)
        self.viewers = dict(clients=0, webrtc_sessions=0, uu_desktop_sessions=0,
                            vnc_connections=0, recording=False, rtsp_service='stopped')
        self.governor = 'performance'
        self.cancel = None
        self.encoding_error = False
        self.short_lease = False
        self.api_error = False
        self.copy_error = False
        self.end_signal_loss = False
        self.stop_failure = False
        self.unit_status = 'LoadState=not-found\nActiveState=inactive'
        self.lose_lease = False
        self.remaining_after_stop = None
        for target, attr, effect in [(quick.bw, 'require_board', lambda: (self.queue, 'ticket')),
                                     (quick.bw, 'ssh', self.ssh), (quick.subprocess, 'run', self.copy)]:
            mock = patch.object(target, attr, side_effect=effect)
            mock.start()
            self.addCleanup(mock.stop)

    def ssh(self, host, command, **kwargs):
        self.events.append(command)
        if command == 'uname -r':
            return '7.3.0-vim4kvm-uhd6+' if self.args.schedutil else '5.15.test'
        if 'random/boot_id' in command:
            return 'test-boot'
        if command.startswith('for f in'):
            return f'/policy0 {self.governor}\n/policy4 {self.governor}'
        if '--phase-state' in command:
            return json.dumps(dict(hdmi=self.hdmi, one_kvm=self.service, **self.viewers))
        if command == 'sudo -n systemctl stop one-kvm':
            self.service = 'inactive'
        if command == 'sudo -n systemctl start one-kvm':
            self.service = 'active'
        if 'sudo -n systemctl stop p0-2-pm-' in command and self.stop_failure:
            raise subprocess.TimeoutExpired(command, 8)
        if command.startswith('systemctl show p0-2-pm-'):
            if self.remaining_after_stop is not None:
                self.item['seconds'] = self.remaining_after_stop
            return self.unit_status
        if 'tee /policy4' in command and self.short_lease:
            self.item['seconds'] = 125
        if command.startswith('timeout ') and '/result' in command:
            if self.lose_lease:
                self.item['state'] = 'expired'
            if self.end_signal_loss:
                self.hdmi['signal'] = False
            if self.cancel:
                os.kill(os.getpid(), self.cancel)
            if self.encoding_error:
                raise RuntimeError('pool allocation')
        if 'api/stream/status' in command and self.api_error:
            raise RuntimeError('API did not become ready')
        return ''

    def copy(self, argv, **kwargs):
        if argv[1].startswith('vim4:'):
            self.events.append('fetch')
            if self.copy_error:
                raise OSError('copy failure')
            output = self.args.output
            (output/'pm.jsonl').write_text(''.join(json.dumps(dict(monotonic_ns=t))+'\n'
                                                  for t in [900, 1300, 1700, 3000]))
            if self.args.phase in ('h264', 'h265'):
                (output/(self.args.phase+'.json')).write_text(json.dumps(dict(
                    success=True, measurement_start_monotonic_us=1, measurement_end_monotonic_us=2)))

    def event(self, prefix):
        return next(i for i, event in enumerate(self.events) if isinstance(event, str) and event.startswith(prefix))

    def test_idle_rejects_unlocked_or_external_viewers_before_sampling(self):
        self.args.phase = 'idle'
        for i, viewer in enumerate(('signal_loss', 'webrtc_sessions', 'uu_desktop_sessions',
                                    'vnc_connections', 'recording', 'rtsp_service')):
            self.args.output = self.args.output.parent / str(i)
            self.hdmi['signal'] = viewer != 'signal_loss'
            self.viewers.update(webrtc_sessions=int(viewer=='webrtc_sessions'),
                                uu_desktop_sessions=int(viewer=='uu_desktop_sessions'),
                                vnc_connections=int(viewer=='vnc_connections'), recording=viewer=='recording',
                                rtsp_service='running' if viewer=='rtsp_service' else 'stopped')
            with self.subTest(reason=viewer), self.assertRaisesRegex(RuntimeError, 'preflight'):
                quick.pm_phase(self.args)
            self.assertTrue(self.events[-1].startswith('rm -rf -- /var/tmp/p0-2-pm-'))
            self.queue.sampling.assert_not_called()
            self.assertFalse(any('tee ' in s or 'stop one-kvm' in s for s in self.events))

    def test_stock_running_performance_allowed_and_block_drift_rejected(self):
        self.args.schedutil = False
        self.args.phase = 'signal'
        quick.pm_phase(self.args)
        self.assertEqual(json.loads((self.args.output/'phase.json').read_text())['governors']['/policy4'], 'performance')
        self.assertFalse(any('tee ' in s for s in self.events if isinstance(s, str)))
        self.governor = 'schedutil'
        self.args.output = self.args.output.parent / 'next'
        with self.assertRaisesRegex(RuntimeError, 'within PM block'):
            quick.pm_phase(self.args)

    def test_interruption_stops_unit_and_recovers_before_fetch(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.events.clear()
            self.args.output = self.args.output.parent / sig.name
            self.cancel = sig
            with self.subTest(signal=sig), self.assertRaises(quick.PMCancelled):
                quick.pm_phase(self.args)
            stop = self.event('systemctl show p0-2-pm-')
            self.assertLess(stop, self.event('echo performance'))
            self.assertLess(self.event('echo performance'), self.event('sudo -n systemctl start one-kvm'))
            self.assertLess(self.event('timeout 20'), self.events.index(('sampling', False)))
            self.assertLess(self.events.index(('sampling', False)), self.event('fetch'))
            self.assertLess(self.event('fetch'), self.event('rm -rf'))

    def test_late_short_lease_does_not_start_work_and_restores_settings(self):
        self.short_lease = True
        with self.assertRaisesRegex(RuntimeError, 'cannot cover'):
            quick.pm_phase(self.args)
        self.assertFalse(any('systemd-run' in s for s in self.events))
        self.assertIn('sudo -n systemctl start one-kvm', self.events)
        self.assertTrue(any('tee /policy4' in s and 'performance' in s for s in self.events))

    def test_api_recovery_and_copy_failures_leave_actionable_evidence(self):
        self.api_error = self.copy_error = True
        with self.assertRaises(ExceptionGroup):
            quick.pm_phase(self.args)
        self.assertIn('API did not become ready', (self.args.output/'recovery-required.json').read_text())
        phase = json.loads((self.args.output/'phase.json').read_text())
        self.assertTrue(phase['retained_remote'].startswith('/var/tmp/p0-2-pm-'))
        self.assertFalse(any('rm -rf' in s for s in self.events))
        self.queue.sampling.assert_called_with('ticket', False)

    def test_bench_and_pm_use_overlapping_board_clock_and_full_57fps_budget(self):
        quick.pm_phase(self.args)
        unit = self.events[self.event('sudo -n systemd-run')]
        deadline = int(re.search(r'--timeout=(\d+)', unit)[1])
        self.assertGreater(deadline, (36000 + 120) / 57)
        self.assertIn(f'timeout -k 3 {deadline + 10}', unit)
        self.assertIn('--bench-done=', unit)
        phase = json.loads((self.args.output/'phase.json').read_text())
        self.assertEqual(phase['common_interval'], dict(start_ns=1300, end_ns=1700, samples=2))
        self.assertNotIn('retained_remote', phase)
        (self.args.output/'pm.jsonl').write_text('{"monotonic_ns": 1500}\n')
        with self.assertRaisesRegex(RuntimeError, 'cover'):
            quick.pm_interval(self.args.output, self.args.phase)

    def test_encoder_failure_preserves_end_snapshot_and_restores_service(self):
        self.encoding_error = True
        with self.assertRaisesRegex(RuntimeError, 'pool allocation'):
            quick.pm_phase(self.args)
        phase = json.loads((self.args.output/'phase.json').read_text())
        self.assertEqual(phase['end']['one_kvm'], 'inactive')
        self.assertIn('sudo -n systemctl start one-kvm', self.events)

    def test_idle_signal_loss_at_end_is_recorded_before_service_restart(self):
        self.args.phase = 'idle'
        self.end_signal_loss = True
        with self.assertRaises(ExceptionGroup):
            quick.pm_phase(self.args)
        phase = json.loads((self.args.output/'phase.json').read_text())
        self.assertIn('end_error', phase)
        self.assertEqual(phase['end']['one_kvm'], 'inactive')
        self.assertEqual(self.service, 'active')

    def test_sampling_request_interrupted_before_ack_is_cleared(self):
        def sampling(ticket, enabled):
            if enabled:
                os.kill(os.getpid(), signal.SIGTERM)
        self.queue.sampling.side_effect = sampling
        with self.assertRaises(quick.PMCancelled):
            quick.pm_phase(self.args)
        self.queue.sampling.assert_called_with('ticket', False)
        self.assertNotIn('sudo -n systemctl stop one-kvm', self.events)

    def test_failed_stop_requires_confirmed_inactive_before_restart(self):
        self.stop_failure = True
        for i, status in enumerate(('LoadState=loaded\nActiveState=active', '', 'LoadState=not-found\nActiveState=inactive')):
            self.events.clear()
            self.service = 'active'
            self.unit_status = status
            self.args.output = self.args.output.parent / str(i)
            if i == 2:
                quick.pm_phase(self.args)
                self.assertEqual(self.service, 'active')
                continue
            with self.subTest(status=status), self.assertRaises(ExceptionGroup):
                quick.pm_phase(self.args)
            self.assertEqual(sum(str(e).startswith('systemctl show p0-2-pm-') for e in self.events), 2)
            self.assertNotIn('sudo -n systemctl start one-kvm', self.events)
            self.assertIn('Confirm p0-2-pm-', (self.args.output/'recovery-required.json').read_text())
            self.assertIn('retained_remote', json.loads((self.args.output/'phase.json').read_text()))

    def test_lost_ticket_skips_end_probe_and_all_remote_cleanup(self):
        self.lose_lease = True
        with self.assertRaises(ExceptionGroup):
            quick.pm_phase(self.args)
        monitor = next(i for i, event in enumerate(self.events) if str(event).startswith('timeout ') and '/result' in event)
        self.assertEqual(self.events[monitor+1:], [('sampling', False)])
        self.assertEqual(json.loads((self.args.output/'phase.json').read_text())['end'], '缺测')

    def test_end_probe_checks_budget_even_after_stop_confirmed(self):
        self.remaining_after_stop = 5
        with self.assertRaises(ExceptionGroup):
            quick.pm_phase(self.args)
        stop = self.event('systemctl show p0-2-pm-')
        self.assertEqual(self.events[stop+1:], [('sampling', False)])
        phase = json.loads((self.args.output/'phase.json').read_text())
        self.assertEqual(phase['end'], '缺测')
        self.assertIn('cannot cover', phase['end_error'])


class QuickRecoveryTest(unittest.TestCase):

    def queue(self):
        queue = Mock()
        queue.read.return_value = dict(sampling=True, state='held', heavy=False,
            started=time.time(), seconds=1800)
        return queue

    def test_native_failure_restores_service_even_if_sampling_cleanup_fails(self):
        queue = self.queue()
        def sampling(ticket,on):
            if not on:raise RuntimeError('sampling off failed')
        queue.sampling.side_effect=sampling

        def ssh(host, command, **kwargs):
            if command == 'systemctl is-active one-kvm':
                return 'active\n'
            if 'timeout -k' in command:
                raise RuntimeError('injected encoder failure')
            return ''

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(quick.bw, 'require_board', return_value=(queue, 'ticket')), \
                patch.object(quick.bw, 'ssh', side_effect=ssh) as remote, \
                patch.object(quick.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'injected') as failure:
                quick.native('stock', Path(folder) / 'run')
            self.assertEqual(remote.call_args.args[1], 'sudo -n systemctl start one-kvm')
            self.assertEqual([c.args for c in queue.sampling.call_args_list],
                             [('ticket', True), ('ticket', False)])
            self.assertIn('sampling off failed',str(failure.exception.__notes__))
            self.assertTrue((Path(folder)/'run/cleanup-errors.json').exists())

    def test_expired_lease_records_handoff_instead_of_unowned_service_restart(self):
        queue=self.queue()
        def ssh(host,command,**kwargs):
            if command=='systemctl is-active one-kvm':return 'active'
            if 'timeout -k' in command:
                queue.read.return_value['state']='expired'
                raise RuntimeError('original measurement failure')
            return ''
        def sampling(ticket,on):
            if not on:raise RuntimeError('board lease ended')
        queue.sampling.side_effect=sampling
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(quick.bw,'require_board',return_value=(queue,'ticket')), \
             patch.object(quick.bw,'ssh',side_effect=ssh) as remote, \
             patch.object(quick.subprocess,'run'):
            output=Path(folder)/'native'
            with self.assertRaisesRegex(RuntimeError,'original measurement') as failure:
                quick.native('edge',output)
            self.assertFalse(any('systemctl start' in call.args[1] for call in remote.call_args_list))
            self.assertEqual(len(json.loads((output/'cleanup-errors.json').read_text())),2)
            self.assertIn('one-kvm',json.loads((output/'recovery-required.json').read_text())['recovery'])
            self.assertIn('board lease ended',str(failure.exception.__notes__))

    def test_insufficient_lease_refuses_before_service_or_copy_operations(self):
        queue=self.queue();queue.read.return_value['seconds']=100
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(quick.bw,'require_board',return_value=(queue,'ticket')), \
             patch.object(quick.bw,'ssh') as remote, \
             patch.object(quick.subprocess,'run') as copy:
            with self.assertRaisesRegex(RuntimeError,'cannot cover'):
                quick.native('edge',Path(folder)/'native')
            remote.assert_not_called();copy.assert_not_called()
            self.assertFalse((Path(folder)/'native').exists())

    def test_remaining_budget_rechecked_between_codecs_and_service_still_restored(self):
        queue=self.queue();benchmarks=[]
        def ssh(host,command,**kwargs):
            if command=='systemctl is-active one-kvm':return 'active'
            if 'timeout -k' in command:
                benchmarks.append(command)
                queue.read.return_value['started']=time.time()-1700
            return ''
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(quick.bw,'require_board',return_value=(queue,'ticket')), \
             patch.object(quick.bw,'ssh',side_effect=ssh) as remote, \
             patch.object(quick.subprocess,'run'):
            with self.assertRaisesRegex(RuntimeError,'cannot cover'):
                quick.native('edge',Path(folder)/'native')
            self.assertEqual(len(benchmarks),1)
            self.assertEqual(remote.call_args.args[1],'sudo -n systemctl start one-kvm')

    def test_receiver_failure_preserved_while_sampling_tunnel_and_return_cleanup_fail(self):
        queue=self.queue();tunnel=Mock()
        tunnel.terminate.side_effect=RuntimeError('tunnel termination failed')
        def sampling(ticket,on):
            if not on:raise RuntimeError('sampling release failed')
        queue.sampling.side_effect=sampling
        def run(command,**kwargs):
            if command[0]=='node':raise RuntimeError('original receiver failure')
            if command[-1]=='return-baseline':raise RuntimeError('return failed')
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(quick,'ROOT',Path(folder)), \
             patch.object(quick,'native'), \
             patch.object(quick.bw,'require_board',return_value=(queue,'ticket')), \
             patch.object(quick.subprocess,'Popen',return_value=tunnel), \
             patch.object(quick.subprocess,'run',side_effect=run), \
             patch.object(quick.time,'sleep'):
            root=Path(folder)/'logs/p0-2-quick';root.mkdir(parents=True)
            (root/'baseline-proof.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'original receiver failure') as failure:
                quick.window(SimpleNamespace(label='fault',candidate=Path('candidate'),sha256='sha',backend='edge'))
            tunnel.terminate.assert_called_once();tunnel.wait.assert_called_once_with(timeout=10)
            notes=str(failure.exception.__notes__)
            for error in ('sampling release failed','tunnel termination failed','return failed'):
                self.assertIn(error,notes)
            self.assertEqual(len(json.loads((root/'fault/cleanup-errors.json').read_text())),3)
