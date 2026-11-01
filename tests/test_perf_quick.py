"""A failed benchmark must release sampling and restore the original service."""
import importlib.util
import json
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
