"""Advance a virtual clock through the actual Window.run finally, without I/O."""
import json
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_hdr10_phase2 import load

window=load('phase2-window')
# Independent elapsed costs of the existing recovery I/O, rather than letting
# a mistakenly reduced production reservation also shorten the simulated I/O.
COSTS={'collect':45,'baseline':300,'reconnect':45,'config':65,'source':120,'sampling':10,'tunnel':10}


class Clock:
    now=0

    def time(self):
        return self.now

    def advance(self,seconds):
        self.now+=seconds


class RecoveryBudgetTest(unittest.TestCase):
    def run_at_recovery_boundary(self,remaining,fail_step=None):
        clock=Clock();events=[]
        queue=Mock();queue.read.return_value=dict(state='held',heavy=False,started=0,seconds=1800)
        m6=Mock();m6.restore_needed=False
        m6.toggle.side_effect=lambda enabled:setattr(m6,'restore_needed',True)
        client=Mock();client.idle.return_value=dict(idle=True)
        tunnel=Mock()

        def consume(name):
            events.append(name)
            clock.advance(COSTS[name])
            if name==fail_step:raise RuntimeError('injected '+name+' failure')

        def restored(*,deadline):
            self.assertEqual(deadline-clock.now,100)
            clock.advance(100)
            m6.restore_needed=False

        m6.restore.side_effect=restored
        def reap(timeout):
            self.assertEqual(timeout,10)
            consume('tunnel')
        tunnel.wait.side_effect=reap
        viewer=Mock()
        def start_viewer(*args,**kwargs):
            events.append('source');clock.advance(5)
            return viewer
        def reap_viewer(timeout):
            clock.advance(timeout)
            if timeout==10:raise window.subprocess.TimeoutExpired('viewer',timeout)
        viewer.wait.side_effect=reap_viewer

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(window,'REPO',Path(tmp)), \
             patch.object(window.time,'time',clock.time), \
             patch.object(window.time,'monotonic',clock.time), \
             patch.object(window.w,'require_board',return_value=(queue,'token')), \
             patch.object(window.w,'MCP',return_value=client), \
             patch.object(window.w,'source_hdr',return_value=False), \
             patch.object(window.g,'M6',return_value=m6), \
             patch.object(window.subprocess,'Popen',side_effect=start_viewer):
            queue.root=Path(tmp)/'queue'
            baseline=Path(tmp)/'files.json';baseline.write_text('[]')
            args=SimpleNamespace(window='boundary',observer=Path('/bin/true'),device='unused',
                panfrost=Path('payload'),panfrost_sha256='sha',baseline_files=baseline,
                url='http://127.0.0.1:18080',local_ip='192.0.2.1')
            runner=window.Window(args)
            runner.start_m6_preview=Mock(return_value=Mock())

            def ssh(host,command,**kwargs):
                if command.startswith('cat '):return '{"api_key":"unit"}'
                parts=shlex.split(command)
                if len(parts)>4 and parts[3].endswith('.py'):
                    operation=parts[4]
                    if operation=='configure':
                        # Inject the recovery entry time. All recovery guards,
                        # their ordering and the real finally remain unmocked.
                        clock.now=1800-remaining
                        raise RuntimeError('injected workload failure')
                    if operation=='restore':
                        self.assertEqual(kwargs['timeout'],65)
                        consume('config')
                    if operation=='status':return '{"taint":0,"cma":{"CmaFree":100}}'
                return ''

            def cli(args,timeout):
                if args[0]=='collect':
                    self.assertEqual(timeout,45);consume('collect')
                if args[0]=='return-baseline':
                    self.assertEqual(timeout,300);consume('baseline')

            def connect(previous=None,recovery=False,reserve_after=0):
                if recovery:
                    runner.require_lease(45+reserve_after)
                    consume('reconnect')
                else:runner.require_work(window.RECOVERY_SECONDS['reconnect'])
                return tunnel

            def monitor(*,target,args,daemon):
                args[1].set()
                return Mock()

            def sampling_off(command,**kwargs):
                self.assertEqual(command[-4:],['sampling','--ticket','token','off'])
                self.assertEqual(kwargs['timeout'],10)
                consume('sampling')

            runner.open_tunnel=connect;runner._cli=cli
            with patch.object(window.w,'ssh',side_effect=ssh), \
                 patch.object(window.threading,'Thread',side_effect=monitor), \
                 patch.object(window.subprocess,'run',side_effect=sampling_off):
                with self.assertRaises(RuntimeError) as raised:runner.run()
            proof=json.loads((runner.output/'recovery.json').read_text())
            return SimpleNamespace(events=events,proof=proof,message=str(raised.exception),
                remaining=1800-clock.now,collection_skipped=(runner.output/'collection-skipped.json').exists())

    def test_work_refuses_old_six_minute_boundary_and_reserves_unwind_and_full_finally(self):
        clock=Clock()
        queue=Mock();queue.read.return_value=dict(state='held',heavy=False,started=0,seconds=1800)
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)), \
             patch.object(window.time,'time',clock.time),patch.object(window.time,'monotonic',clock.time), \
             patch.object(window.w,'require_board',return_value=(queue,'token')):
            runner=window.Window(SimpleNamespace(window='work-boundary'))
            expected=sum(COSTS.values())+max(65,15+16+15+12)+15
            self.assertEqual(runner.deadline,1800-expected)
            clock.now=1800-361
            with self.assertRaises(RuntimeError):runner.require_work()
            late=window.Window(SimpleNamespace(window='late-start'))
            with self.assertRaisesRegex(RuntimeError,'lease cannot cover'):late.require_work()
            clock.now=1800-expected-65
            runner.require_work(65)
            clock.advance(65)
            runner.require_work()
            clock.advance(.01)
            with self.assertRaises(RuntimeError):runner.require_work()

    def test_maximum_finally_costs_restore_m6_and_cleanup_with_reserved_unwind_spent(self):
        remaining=window.RECOVERY_RESERVE-window.UNWIND_SECONDS
        result=self.run_at_recovery_boundary(remaining)
        self.assertEqual(result.events,['collect','baseline','reconnect','config','source','sampling','tunnel'])
        self.assertEqual(result.proof['errors'],[])
        self.assertFalse(result.proof['source_recovery_pending'])
        self.assertEqual(result.message,'injected workload failure')
        self.assertEqual(result.remaining,15)

    def test_reconnect_checks_later_restore_budget_before_touching_the_old_tunnel(self):
        clock=Clock()
        queue=Mock();queue.read.return_value=dict(state='held',heavy=False,started=0,seconds=1800)
        tail=65+120+20
        clock.now=1800-(45+tail-1)
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)), \
             patch.object(window.time,'time',clock.time), \
             patch.object(window.w,'require_board',return_value=(queue,'token')), \
             patch.object(window.subprocess,'Popen') as start:
            runner=window.Window(SimpleNamespace(window='reconnect-boundary'))
            previous=Mock()
            with self.assertRaisesRegex(RuntimeError,'lease cannot cover'):
                runner.open_tunnel(previous,recovery=True,reserve_after=tail)
            previous.terminate.assert_not_called();start.assert_not_called()

    def test_optional_collection_skipped_at_exact_mandatory_budget(self):
        result=self.run_at_recovery_boundary(window.REQUIRED_RECOVERY_SECONDS)
        self.assertEqual(result.events,['baseline','reconnect','config','source','sampling','tunnel'])
        self.assertTrue(result.collection_skipped)
        self.assertFalse(result.proof['source_recovery_pending'])
        self.assertEqual(result.proof['errors'],[])
        self.assertEqual(result.remaining,0)

    def test_earlier_step_must_not_spend_later_source_and_cleanup_budget(self):
        result=self.run_at_recovery_boundary(window.REQUIRED_RECOVERY_SECONDS-1)
        self.assertNotIn('baseline',result.events)
        self.assertEqual(result.events,['reconnect','config','source','sampling','tunnel'])
        self.assertTrue(result.collection_skipped)
        self.assertFalse(result.proof['source_recovery_pending'])
        self.assertTrue(any('baseline:' in error for error in result.proof['errors']))

    def test_failed_collection_or_baseline_preserves_budget_for_later_restoration(self):
        for failed in ('collect','baseline'):
            with self.subTest(failed=failed):
                result=self.run_at_recovery_boundary(window.RECOVERY_RESERVE-window.UNWIND_SECONDS,failed)
                self.assertFalse(result.proof['source_recovery_pending'])
                self.assertEqual(result.events[-3:],['source','sampling','tunnel'])
                self.assertIn('injected '+failed+' failure',result.message)
                self.assertEqual(result.remaining,15)

    def test_local_cleanup_failures_do_not_skip_the_other_local_cleanup(self):
        result=self.run_at_recovery_boundary(window.RECOVERY_RESERVE-window.UNWIND_SECONDS,'sampling')
        self.assertFalse(result.proof['source_recovery_pending'])
        self.assertEqual(result.events[-2:],['sampling','tunnel'])
        self.assertIn('injected sampling failure',result.message)
