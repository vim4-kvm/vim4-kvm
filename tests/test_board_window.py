import base64
import http.server
import importlib.machinery
import importlib.util
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('window_tool', str(ROOT / 'tools/board-window'))
spec = importlib.util.spec_from_loader('window_tool', loader)
window = importlib.util.module_from_spec(spec)
loader.exec_module(window)


class WindowTests(unittest.TestCase):
    def test_baseline_reboot_reason_does_not_relax_other_identity(self):
        before = dict(release='5.15.test', build_id='a'*40, files={'/boot/Image':'hash'},
                      cmdline='root=PARTUUID=abcd reboot_mode=watchdog_reboot rw')
        after = dict(before, cmdline='root=PARTUUID=abcd reboot_mode=normal rw')
        window.verify_baseline(before, after)
        invalid = [dict(after, build_id='b'*40), dict(after, files={}),
                   dict(after, release='7.3.test'),
                   dict(after, cmdline=after['cmdline']+' init=/other'),
                   dict(after, cmdline=after['cmdline']+' reboot_mode=normal'),
                   dict(after, cmdline=after['cmdline'].replace('normal','unknown'))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                window.verify_baseline(before, value)

    def test_large_inventory_cleanup_fits_linux_exec_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / 'cleanup.py'
            module.write_text('def cleanup_module_mountpoint(plan):\n    print(plan["release"], plan.get("payload_id", "legacy"))\n')
            legacy = dict(build_id='1' * 40, release='7.3.0-vim4kvm-uhd4+',
                          files={str(i): 'a' * 64 for i in range(4000)})
            current = dict(legacy, namespace='kbase', payload_id='default')
            script = window.module_cleanup_script([legacy, current], str(module))
            self.assertLess(len(script.encode()), 128 * 1024)
            output = subprocess.check_output([sys.executable, '-c', script], text=True)
            self.assertEqual(output.splitlines(), ['7.3.0-vim4kvm-uhd4+ legacy',
                                                  '7.3.0-vim4kvm-uhd4+ default'])

    def test_recovery_retains_each_payload_with_same_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kernel = '1' * 40
            first = dict(build_id=kernel, namespace='kbase', payload_id='default')
            second = dict(first, payload_id='coherent')
            legacy = dict(build_id=kernel)
            for plan in (first, second, legacy):
                window.record_candidate(root, plan, 'a' * 64)
            recovered = [json.loads(p.read_text()) for p in root.glob('candidate-*.json')]
            self.assertEqual(len(recovered), 3)
            self.assertEqual({p.get('payload_id') for p in recovered}, {'default', 'coherent', None})
            self.assertTrue((root / ('candidate-' + kernel + '.json')).exists())

    def test_m6_tolerates_unknown_metadata_during_both_transitions(self):
        client = window.MCP('unused', 'test')
        client.call = Mock()
        client.screenshot = Mock(return_value={'content': [{'type': 'text', 'text': 'Screen 1920x1080'}]})
        client.idle = Mock(return_value={'idle': True})
        states = iter([False, False, window.UnknownHDRState('transition'), True,
                       True, window.UnknownHDRState('transition'), False])
        def read_state():
            state = next(states)
            if isinstance(state, Exception):
                raise state
            return state
        with tempfile.TemporaryDirectory() as directory, patch.object(window.time, 'sleep'):
            client.m6_hdr(True, Path(directory), read_state, [])
        toggles = [c for c in client.call.call_args_list
                   if c.args == ('left_click', {'coordinate': [1704, 540]})]
        self.assertEqual(len(toggles), 2)

    def test_autoboot_is_read_before_reboot_ssh_exits(self):
        uart = Mock()
        uart.open_port.return_value = 42
        chunks = [b'Hit SPACE in 2 seconds', b'kvim4#', b'login:']
        process = Mock()
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window, 'load', return_value=uart), \
                patch.object(window, 'ssh', side_effect=['old-boot', 'c8:63:14:74:70:0d']), \
                patch.object(window.subprocess, 'Popen', return_value=process), \
                patch.object(window.select, 'select', return_value=([42], [], [])), \
                patch.object(window.os, 'read', side_effect=chunks), \
                patch.object(window.os, 'write') as write, \
                patch.object(window.os, 'close'), patch.object(window, 'ready') as ready:
            window.boot('mock', 'serial', Path(directory), dict(command='sysboot candidate', release='candidate'))
        self.assertEqual([c.args[1] for c in write.call_args_list],
                         [b' ', b'setenv ethaddr c8:63:14:74:70:0d; sysboot candidate\n'])
        ready.assert_called_once_with('mock', expected='candidate', old_boot='old-boot')
        process.terminate.assert_called_once()

    def test_m6_recipe_restores_actual_source_state_on_failure(self):
        client = window.MCP('unused', 'test')
        state = [False]
        def action(name, arguments):
            if name == 'left_click' and arguments['coordinate'] == [1704, 540]:
                state[0] = not state[0]
        client.call = Mock(side_effect=action)
        client.screenshot = Mock(return_value={'content': [{'type': 'text', 'text': 'Screen 1920x1080 (source 3840x2160).'}]})
        client.idle = Mock(return_value={'idle': True})
        with tempfile.TemporaryDirectory() as directory, patch.object(window.time, 'sleep'), patch.object(window.subprocess, 'run', side_effect=RuntimeError('failed sample')):
            with self.assertRaisesRegex(RuntimeError, 'failed sample'):
                client.m6_hdr(True, Path(directory), lambda: state[0], ['false'])
        self.assertFalse(state[0])
        self.assertEqual(client.screenshot.call_args.args[0].name, 'm6-restored.jpg')

    def test_hdr2_payload_stages_privately_with_executable_helpers(self):
        self.stage_private_payload('7.3.0-vim4kvm-uhd4r2+')

    def test_generic_release_stages_and_cleans_only_its_empty_mountpoint(self):
        self.stage_private_payload('7.3.0-vim4kvm-future_hdr10.r42+')

    def stage_private_payload(self, release):
        from test_display_once import static_elf
        once = window.load('payload_stage', ROOT / 'packaging/kernel-edge/display-once.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate = root / 'hdr2-unified' / ('a'*40)
            files = {'Image': b'kernel', 'vim4.dtb': b'dtb', 'init': static_elf(),
                     f'modules/{release}/test.ko': b'module',
                     'runtime/helper': b'#!/bin/sh\nexit 0\n',
                     'extlinux.conf': (f'LINUX {candidate}/Image\nFDT {candidate}/vim4.dtb\nAPPEND init={candidate}/init\n').encode()}
            manifest = dict(release=release, build_id='a'*40, source_commit='b'*40,
                            sha256={name: once.hashlib.sha256(data).hexdigest() for name, data in files.items()})
            bundle = root / 'payload.tar.gz'
            with tarfile.open(bundle, 'w:gz') as archive:
                for name, data in dict(files, **{'manifest.json': json.dumps(manifest).encode()}).items():
                    member = tarfile.TarInfo('./' + name)
                    member.mode = 0o755 if name.startswith('runtime/') else 0o644
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            baseline = root / 'baseline'
            baseline.write_bytes(b'unchanged')
            proof = dict(release='5.15.test', build_id='c'*40, cmdline='baseline', files={str(baseline): once.sha(baseline)})
            lstat = Path.lstat
            def owned(path):
                values = list(lstat(path)); values[4] = 0; values[0] &= ~0o022
                return os.stat_result(values)
            (root / 'module-mounts').mkdir()
            with patch.object(once, 'ROOT', root / 'display-m1'), patch.object(once, 'MODULE_ROOT', root / 'module-mounts'), patch.object(once.os, 'geteuid', return_value=0), patch.object(Path, 'lstat', owned):
                once.stage(bundle, retained_baseline=proof)
            self.assertEqual(list((root / 'module-mounts' / manifest['release']).iterdir()), [])
            self.assertTrue((candidate / 'runtime/helper').stat().st_mode & 0o111)
            self.assertEqual(baseline.read_bytes(), b'unchanged')
            with patch.object(once, 'ROOT', root / 'display-m1'), patch.object(once, 'MODULE_ROOT', root / 'module-mounts'), patch.object(once.os, 'geteuid', return_value=0), patch.object(once.os, 'uname', return_value=type('Kernel', (), {'release': '5.15.test'})()):
                mountpoint = root / 'module-mounts' / release
                (mountpoint / 'owned-by-someone-else').touch()
                with self.assertRaises(OSError):
                    once.cleanup_module_mountpoint(manifest)
                (mountpoint / 'owned-by-someone-else').unlink()
                candidate.chmod(0o755)
                once.cleanup_module_mountpoint(manifest)
                self.assertFalse(mountpoint.exists())
            for path in [candidate, *candidate.rglob('*')]:
                if path.is_dir():
                    path.chmod(0o755)

    def test_retained_baseline_gate_allows_chaining_but_rejects_changes(self):
        once = window.load('trial_gate', ROOT / 'packaging/kernel-edge/display-once.py')
        proof = dict(release='5.15.test', build_id='a'*40, cmdline='root=PARTUUID=test',
                     files={'/boot/Image': 'digest'})
        plan = dict(baseline_release=proof['release'], baseline_id=proof['build_id'],
                    baseline_cmdline=proof['cmdline'], baseline_files=proof['files'])
        with patch.object(once.os, 'geteuid', return_value=0), patch.object(once, 'sha', return_value='digest'):
            once.retained_preflight(plan, proof)
            with self.assertRaises(RuntimeError):
                once.retained_preflight(dict(plan, baseline_id='b'*40), proof)
            with patch.object(once, 'sha', return_value='changed'), self.assertRaises(RuntimeError):
                once.retained_preflight(plan, proof)

    def test_readiness_waits_for_services_udc_and_frames(self):
        with patch.object(window, 'ssh', side_effect=[subprocess.CalledProcessError(1, 'not ready'), 'ready']) as ssh, patch.object(window.time, 'sleep'):
            window.ready('mock', expected='7.3.test', old_boot='previous')
        self.assertEqual(ssh.call_count, 2)
        command = ssh.call_args.args[1]
        self.assertIn('configured', command)
        self.assertIn('fps', command)
        self.assertIn('previous', command)

    def test_baseline_daily_cache_and_hash_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = window.BaselineCache(Path(directory) / 'cache.json')
            proof = dict(release='5.15.test', files={'Image': 'a', 'program': 'b', 'boot': 'c'})
            measure = Mock(return_value={'fps': 60})
            first = cache.get(proof, measure, '2026-10-31')
            hit = cache.get(proof, measure, '2026-10-31')
            self.assertTrue(hit['reused'])
            self.assertEqual(first['source_time'], hit['source_time'])
            self.assertEqual(measure.call_count, 1)
            for name in proof['files']:
                changed = dict(proof, files=dict(proof['files'], **{name: 'changed'}))
                self.assertFalse(cache.get(changed, measure, '2026-10-31')['reused'])
            self.assertFalse(cache.get(proof, measure, '2026-11-01')['reused'])
            with self.assertRaises(ValueError):
                cache.get(dict(proof, release='7.3.test'), measure)

    def test_failed_measurement_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = window.BaselineCache(Path(directory) / 'cache.json')
            with self.assertRaises(RuntimeError):
                cache.get(dict(release='5.15.test', files={}), Mock(side_effect=RuntimeError))
            self.assertFalse(cache.path.exists())

    def test_mcp_reinitializes_after_server_restart(self):
        calls = []
        class Handler(http.server.BaseHTTPRequestHandler):
            generation = 0
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(body['method'])
                if body['method'] == 'initialize':
                    Handler.generation += 1
                    self.send_response(200)
                    self.send_header('Mcp-Session-Id', str(Handler.generation))
                    self.end_headers()
                    self.wfile.write(b'{"result":{}}')
                elif body['method'] == 'notifications/initialized':
                    self.send_response(202)
                    self.end_headers()
                elif Handler.generation == 1:
                    self.send_error(404, 'expired session')
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"result":{"content":[]}}')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = window.MCP('http://127.0.0.1:' + str(server.server_port), 'test')
            self.assertEqual(client.call('screenshot'), {'content': []})
            self.assertEqual(calls, ['initialize', 'notifications/initialized', 'tools/call',
                                     'initialize', 'notifications/initialized', 'tools/call'])
            self.assertEqual(client.session, '2')
            window.MCP(client.url, 'test').call('screenshot')
            self.assertEqual(calls[-3:], ['initialize', 'notifications/initialized', 'tools/call'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_hdr_restores_after_command_failure_and_takes_evidence(self):
        client = window.MCP('unused', 'test')
        client.call = Mock()
        client.screenshot = Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(window.subprocess, 'run', side_effect=RuntimeError):
            profile = dict(verified_source='reviewed fixture', apply=[dict(name='left_click')],
                           restore=[dict(name='key', arguments={'text': 'Escape'})])
            with self.assertRaises(RuntimeError):
                client.hdr(profile, Path(directory), ['false'])
        self.assertEqual(client.call.call_args.args[0], 'key')
        self.assertEqual(client.screenshot.call_count, 3)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for receiver timing replay')
    def test_receiver_only_times_after_decoded_frame(self):
        script = r'''
import assert from 'node:assert/strict';
import {measureDecoded} from './tools/board-window-timing.mjs';
let clock=0;
const options={now:()=>clock, sleep:async ms=>{clock+=ms},readyTimeoutMs:1000};
const result=await measureDecoded(async()=>clock<500?null:{id:'v',ssrc:1,framesDecoded:1+(clock-500)/50},.2,options);
assert.equal(result.elapsedMs,200);
assert.equal(result.samples[0].framesDecoded,1);
assert.equal(result.samples.length,5);
clock=0;
await assert.rejects(measureDecoded(async()=>({framesDecoded:0}),.2,options),/No actual decoded/);
clock=0;
await assert.rejects(measureDecoded(async()=>({id:'v',ssrc:clock?2:1,framesDecoded:1}),.2,options),/stream changed/);
'''
        subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
