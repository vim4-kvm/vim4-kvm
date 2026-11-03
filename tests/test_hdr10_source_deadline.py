"""The real source-recovery step shares 120 seconds, including viewer exit."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_hdr10_phase2 import load, SCREENS
from test_hdr10_recovery_budget import Clock

window=load('phase2-window')


class SourceDeadlineTests(unittest.TestCase):
    def exercise(self,last_source_cost):
        clock=Clock();screens=[];source_timeouts=[];observer_timeouts=[]
        queue=Mock();queue.read.return_value=dict(state='held',heavy=False,started=0,seconds=140)
        client=Mock();viewer=Mock();viewer.poll.return_value=None
        def consume(cost,timeout):
            clock.advance(min(cost,timeout))
            if cost>timeout:raise TimeoutError('injected bounded I/O timeout')
        def screenshot(path,*,deadline):
            screens.append(deadline)
            if len(screens)==1:
                consume(19,deadline-clock.now)
                raise RuntimeError('No video signal')
            if len(screens)>2:consume(20,deadline-clock.now)
        client.screenshot.side_effect=screenshot
        def source(*,timeout):
            source_timeouts.append(timeout)
            if len(source_timeouts)>1:consume(last_source_cost,timeout)
            return False
        def observer(command,*,text,timeout):
            observer_timeouts.append(timeout)
            consume(10 if len(observer_timeouts)==1 else 30,timeout)
            return json.dumps(SCREENS['chrome'])
        def start(*args,**kwargs):
            clock.advance(5)
            return viewer
        def wait(*,timeout):
            consume(timeout,timeout)
            if timeout==10:raise subprocess.TimeoutExpired('viewer',timeout)
        viewer.wait.side_effect=wait
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)), \
             patch.object(window.time,'monotonic',clock.time), \
             patch.object(window.time,'time',clock.time), \
             patch.object(window.time,'sleep',clock.advance), \
             patch.object(window.w,'require_board',return_value=(queue,'held')), \
             patch.object(window.subprocess,'Popen',side_effect=start), \
             patch.object(window.g.subprocess,'check_output',side_effect=observer):
            runner=window.Window(SimpleNamespace(window='source',url='http://localhost:18080',local_ip='192.0.2.1'))
            m6=window.g.M6(client,source,'/observer',Path(tmp)/'m6')
            m6.initial_hdr=False;m6.restore_needed=True
            if last_source_cost>.75:
                with self.assertRaisesRegex(TimeoutError,'bounded I/O'):runner.restore_source(m6,20)
                self.assertTrue(m6.restore_needed)
            else:
                runner.restore_source(m6,20)
                self.assertFalse(m6.restore_needed)
        client.call.assert_not_called()
        viewer.terminate.assert_called_once();viewer.kill.assert_called_once()
        self.assertEqual(screens,[25,25,105,105])
        self.assertEqual(observer_timeouts,[30,30])
        self.assertEqual(source_timeouts,[30,.75])
        self.assertEqual([c.kwargs['timeout'] for c in viewer.wait.call_args_list],[10,5])
        self.assertLessEqual(clock.now,120)
        self.assertGreaterEqual(140-clock.now,20)
        return clock.now

    def test_actual_restore_and_slow_viewer_exit_finish_inside_shared_budget(self):
        self.assertEqual(self.exercise(.5),119.75)

    def test_slow_source_read_is_cut_off_before_consuming_cleanup_budget(self):
        self.assertEqual(self.exercise(120),120)

    def test_mcp_initialize_and_tool_call_share_the_absolute_deadline(self):
        clock=Clock();requests=[]
        class Response(io.BytesIO):
            headers={}
        def opener(request,*,timeout):
            requests.append((json.loads(request.data)['method'],timeout))
            clock.advance(min(3,timeout))
            if timeout<3:raise TimeoutError('bounded HTTP timeout')
            return Response(b'{"result":{}}')
        client=window.w.MCP('http://localhost/mcp','test',opener=opener)
        with patch.object(window.time,'monotonic',clock.time):
            with self.assertRaises(TimeoutError):client.call('left_click',deadline=5)
            with self.assertRaises(TimeoutError):client.call('left_click',deadline=5)
        self.assertEqual(requests,[('initialize',5),('notifications/initialized',2)])
        self.assertEqual(clock.now,5)


if __name__=='__main__':unittest.main()
