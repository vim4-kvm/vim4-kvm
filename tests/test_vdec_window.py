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


SOURCE = Path(__file__).resolve().parents[1] / 'packaging/kernel/vdec-window.py'
SPEC = importlib.util.spec_from_file_location('vdec_window', SOURCE)
window = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(window)


class DecoderWindowTests(unittest.TestCase):
    @staticmethod
    def encoder_trace(count=600, fps=60):
        return '\n'.join(
            f' encoder:src-1224 [003] ..... {21 + i / fps:.6f}: v4l2_dqbuf: '
            f'minor = 4, index = {i % 4}, type = VIDEO_CAPTURE_MPLANE, flags = DONE'
            for i in range(count))

    def test_encoder_activity_uses_only_selected_capture_dqbuf(self):
        trace = self.encoder_trace() + '\n' + '\n'.join([
            ' other-1 [001] ..... 31.0: v4l2_dqbuf: minor = 14, '
            'type = VIDEO_CAPTURE_MPLANE, flags = ERROR',
            ' encoder-1 [001] ..... 31.0: v4l2_dqbuf: minor = 4, '
            'type = VIDEO_OUTPUT_MPLANE, flags = ERROR',
            ' encoder-1 [001] ..... 31.0: v4l2_qbuf: minor = 4, '
            'type = VIDEO_CAPTURE_MPLANE, flags = ERROR'])
        # No vb2 events: these DQBUF events alone prove completed frames.
        report = window.encoder_capture_statistics(trace, 4)
        self.assertEqual(report['capture_completions'], 600)
        self.assertAlmostEqual(report['fps'], 60, places=4)
        self.assertEqual(report['errors'], [])
        window.require_encoder_capture_activity(report)

    def test_encoder_activity_rejects_absent_short_slow_and_error_capture(self):
        traces = ['', self.encoder_trace(count=569), self.encoder_trace(fps=30),
                  self.encoder_trace().replace('flags = DONE', 'flags = ERROR', 1)]
        for trace in traces:
            with self.subTest(trace=trace[:100]):
                report = window.encoder_capture_statistics(trace, 4)
                with self.assertRaises(RuntimeError):
                    window.require_encoder_capture_activity(report)

    def test_encoder_activity_rejects_malformed_completion_timestamp(self):
        with self.assertRaisesRegex(ValueError, 'completion timestamp'):
            window.encoder_capture_statistics(
                'v4l2_dqbuf: minor = 4, type = VIDEO_CAPTURE_MPLANE', 4)

    def test_obsolete_hevc_preflight_plan_is_rejected_before_hardware_access(self):
        plan = {'board_window': 'candidate', 'kernel': 'mainline', 'hevc': True,
                'hevc_diagnostic_api': 'debugfs-v1'}
        with patch.object(window, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'Obsolete HEVC preflight'):
                window.validate_acceptance_plan(plan, {'source': 'candidate'})
            execute.assert_not_called()

    def test_normal_module_load_needs_no_opt_in_or_preflight(self):
        proof = {'source': 'candidate', 'kernel_build_id': 'image', 'release': '7.3.test',
                 'modules': {'kernel/aml.ko': 'hash'}}
        module = '/lib/modules/7.3.test/kernel/aml.ko'
        private = {'path': module, 'image_build_id': 'image', 'base_revision': 'candidate',
                   'patch': '/tmp/change.patch', 'vermagic': '7.3.test SMP', 'build_id': 'module'}
        for is_private in (False, True):
            plan = {'kernel': 'mainline', 'hevc': True, 'files': {module: 'hash',
                    '/tmp/change.patch': 'hash'}}
            if is_private:
                plan['private_driver'] = private
            def execute(*command, **kwargs):
                return {('modinfo', '-n', 'aml_vdec_drv'): module,
                        ('modinfo', '-F', 'vermagic', module): '7.3.test SMP'}.get(command, '')
            with self.subTest(private=is_private), \
                    patch.object(window.Path, 'glob', return_value=[]), \
                    patch.object(window.Path, 'exists', return_value=False), \
                    patch.object(window, 'sha', return_value='hash'), \
                    patch.object(window, 'build_id', return_value='module'), \
                    patch.object(window, 'run', side_effect=execute) as run, \
                    patch.object(window, 'probe_runtime_pm') as probe:
                window.prepare_acceptance_decoder(plan, proof)
                probe.assert_called_once_with()
                loads = [c.args for c in run.call_args_list if c.args[0] in ('modprobe', 'insmod')]
                self.assertEqual(loads, [('insmod', module)] if is_private else
                                 [('modprobe', 'aml_vdec_drv')])

    def test_runtime_probe_opens_nodes_and_checks_suspend_without_test_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            (device / 'power_state').write_text('VDEC[4]=1 NIC3[39]=1\n')
            with patch.object(window, 't7_device', return_value=device), \
                    patch.object(window, 'require_suspended') as suspended, \
                    patch.object(window, 'faulted', return_value=False), \
                    patch.object(window, 'run') as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                window.probe_runtime_pm()
                self.assertEqual(suspended.call_count, 2)
                script = run.call_args.args[2]
                self.assertIn('os.open(', script)
                self.assertIn('os.close(', script)
                self.assertIn('aml_hevc_decoder', script)

    def test_preserved_probe_releases_encoders_without_reloading_decoder(self):
        plan = {'kernel': 'mainline', 'preserve_decoder_probe': True}
        proof = {'release': '7.3.test', 'modules': {'kernel/aml.ko': 'hash'},
                 'module_build_ids': {'kernel/aml.ko': 'module'}}
        module = '/lib/modules/7.3.test/kernel/aml.ko'
        for loaded_id in ('module', 'wrong'):
            with self.subTest(loaded_id=loaded_id), \
                    patch.object(window.Path, 'glob', return_value=[]), \
                    patch.object(window.Path, 'exists', return_value=True), \
                    patch.object(window.Path, 'is_symlink', return_value=True), \
                    patch.object(window, 't7_device', return_value=Path('/device')), \
                    patch.object(window, 'sha', return_value='hash'), \
                    patch.object(window, 'build_id', return_value=loaded_id), \
                    patch.object(window, 'run', return_value=module) as run, \
                    patch.object(window, 'probe_runtime_pm') as probe:
                if loaded_id == 'wrong':
                    with self.assertRaisesRegex(ValueError, 'Bound decoder build ID'):
                        window.prepare_acceptance_decoder(plan, proof)
                    probe.assert_not_called()
                else:
                    window.prepare_acceptance_decoder(plan, proof)
                    probe.assert_called_once_with()
                loads = [c.args for c in run.call_args_list if c.args[0] in ('modprobe', 'insmod')]
                self.assertEqual(loads, [('modprobe', '-r', 'wave5'),
                                         ('modprobe', '-r', 't7_jpeg')])

    def test_preserved_probe_refuses_unbound_or_mixed_modules_before_stopping_app(self):
        cases = [({'kernel': 'vendor'}, True),
                 ({'kernel': 'mainline', 'private_driver': {'path': '/private'}}, True),
                 ({'kernel': 'mainline', 'coexistence': True}, True),
                 ({'kernel': 'mainline'}, False)]
        for options, bound in cases:
            plan = dict(options, preserve_decoder_probe=True)
            with self.subTest(options=options, bound=bound), \
                    patch.object(window.Path, 'exists', return_value=True), \
                    patch.object(window.Path, 'is_symlink', return_value=bound), \
                    patch.object(window, 't7_device', return_value=Path('/device')), \
                    patch.object(window, 'run') as run:
                with self.assertRaises(ValueError):
                    window.prepare_acceptance_decoder(plan, {})
                run.assert_not_called()

    def test_retired_register_actions_are_rejected_at_cli_parsing(self):
        for action in ('power', 'mdec', 'snapshot'):
            with self.subTest(action=action):
                result = subprocess.run([sys.executable, str(SOURCE), action, '--execute'],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn('invalid choice', result.stderr)

    def test_run_plan_retargets_all_search_paths_and_rejects_stale_directories(self):
        original = {'board_window': 'hwdecode-parity-r66', 'environment': {
            'GST_PLUGIN_PATH': '/var/tmp/hwdecode-standard-r66/official:/var/tmp/hwdecode-standard-r65/plugins',
            'LD_LIBRARY_PATH': '/var/tmp/hwdecode-standard-r65/lib:/var/tmp/hwdecode-standard-r66/lib2:/usr/lib',
            'GST_REGISTRY': '/var/tmp/hwdecode-standard-r66/registry.bin'},
            'video_check': ['python3', '/workspace/build/run52/video.py'],
            'files': {'/var/tmp/hwdecode-standard-r65/input': 'sha'}}
        with self.assertRaisesRegex(ValueError, 'Stale run directory'):
            window.require_current_run_paths(original)
        result = window.retarget_run_plan(original, 67)
        self.assertEqual(result['environment'], {
            'GST_PLUGIN_PATH': '/var/tmp/hwdecode-standard-r67/official:/var/tmp/hwdecode-standard-r67/plugins',
            'LD_LIBRARY_PATH': '/var/tmp/hwdecode-standard-r67/lib:/var/tmp/hwdecode-standard-r67/lib2:/usr/lib',
            'GST_REGISTRY': '/var/tmp/hwdecode-standard-r67/registry.bin'})
        self.assertEqual(result['video_check'][1], '/workspace/build/run67/video.py')
        for key in ('GST_PLUGIN_PATH', 'LD_LIBRARY_PATH', 'GST_REGISTRY'):
            broken = window.retarget_run_plan(original, 67)
            broken['environment'][key] += ':/var/tmp/hwdecode-standard-r65/stale'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Stale run directory'):
                window.require_current_run_paths(broken)
        result['nested'] = [{'source': '/workspace/run66/old'}]
        with self.assertRaisesRegex(ValueError, 'Stale run directory'):
            window.require_current_run_paths(result)

    def test_incremental_journal_preserves_anchor_and_stops_on_new_warning(self):
        def record(cursor, message):
            return json.dumps({'__CURSOR': cursor, 'MESSAGE': message}) + '\n'
        chunks = iter([record('a', 'boot'), record('a', 'boot'),
                       record('a', 'boot') + record('b', 'WARNING: CPU: 1 PID: 2')])
        commands = []
        def collect(command, **kwargs):
            commands.append(command)
            kwargs['stdout'].write(next(chunks))
        with tempfile.TemporaryDirectory() as directory, patch.object(window.subprocess, 'run', side_effect=collect):
            output = Path(directory)
            with window.incremental_kernel_journal(output):
                window.require_clean_kernel_log(output)
                window.require_clean_kernel_log(output)
                self.assertEqual((output / 'kernel.log').read_text().count('boot'), 1)
                with self.assertRaisesRegex(RuntimeError, 'diagnostic failure'):
                    window.require_clean_kernel_log(output)
                self.assertIn('WARNING:', (output / 'kernel-journal-0003.jsonl').read_text())
                self.assertEqual((output / 'kernel-journal.cursor').read_text(), 'a\n')
            self.assertIsNone(window._kernel_journal_reader)
            self.assertIn('--cursor=a', commands[1])

    def test_incremental_journal_lost_cursor_and_command_timeout_fail_closed(self):
        for failure in ('cursor', 'timeout', 'truncated'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                reader = window.KernelJournal(output)
                reader.cursor = 'saved'
                def collect(command, **kwargs):
                    if failure == 'timeout':
                        kwargs['stdout'].write('partial evidence\n')
                        raise subprocess.TimeoutExpired(command, 15)
                    kwargs['stdout'].write('{' if failure == 'truncated' else
                        json.dumps({'__CURSOR': 'later', 'MESSAGE': 'normal'}))
                with patch.object(window.subprocess, 'run', side_effect=collect) as execute:
                    with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                        reader.read()
                    with self.assertRaisesRegex(RuntimeError, 'previously failed'):
                        reader.read()
                    self.assertEqual(execute.call_count, 1)
                self.assertEqual(reader.cursor, 'saved')
                self.assertTrue((output / 'kernel-journal-0001.error').exists())
                self.assertTrue((output / 'kernel-journal-0001.jsonl').exists())

    def test_baseline_plan_rejects_stale_missing_or_extra_protected_files(self):
        files = {'/boot/extlinux/extlinux.conf': 'new', '/boot/Image': 'image'}
        window.require_plan_baseline({'protected_files': dict(files)}, {'files': files})
        for invalid in ({**files, '/boot/extlinux/extlinux.conf': 'old'},
                        {'/boot/Image': 'image'}, {**files, '/old/module': 'old'}, {}):
            with self.subTest(files=invalid), self.assertRaisesRegex(ValueError, 'exactly match'):
                window.require_plan_baseline({'protected_files': invalid}, {'files': files})
        with self.assertRaises(ValueError):
            window.require_plan_baseline({'protected_files': {}}, {'files': {}})

    def test_disabled_lockdep_cannot_pass_joint_debug_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(window.Path, 'read_text', return_value=' debug_locks: 0\n'), \
                    self.assertRaisesRegex(RuntimeError, 'no longer checking'):
                window.require_joint_debug_state(output, 'startup')
            self.assertEqual((output / 'startup-lockdep.log').read_text(), ' debug_locks: 0\n')

    def test_startup_diagnostic_failure_is_preserved_and_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for message in ('DMA-API: debugging enabled by kernel config\n',
                            'WARNING: possible circular locking dependency detected\n',
                            'BUG: KASAN: vmalloc-out-of-bounds in strchr+0x3c/0x80\n'):
                with self.subTest(message=message), patch.object(window, 'run', return_value=message):
                    if message.startswith('DMA-API: debugging'):
                        window.require_clean_kernel_log(output)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Kernel diagnostic failure'):
                            window.require_clean_kernel_log(output)
                    self.assertEqual((output / 'kernel.log').read_text(), message)

    def test_fluster_missing_result_cannot_pass_on_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.json'
            for content in (None, {}, {'test_suites': {}}):
                if content is not None:
                    path.write_text(json.dumps(content))
                with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'Missing or malformed'):
                    window.fluster_result(path, 'suite', 'decoder', 'vector')
            for status in ('Not run', 'Not supported', 'Timeout', 'Fail'):
                path.write_text(json.dumps({'test_suites': {'suite': {'decoders': {
                    'decoder': {'vectors': {'vector': {'result': status, 'time': 0}}}}}}}))
                self.assertEqual(window.fluster_result(path, 'suite', 'decoder', 'vector')['result'], status)

    def test_fluster_timeout_stops_before_the_next_vector(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'results'
            output.mkdir()
            manifest = root / 'bundle-manifest.json'
            manifest.write_text(json.dumps({'fluster_revision': 'locked', 'files': {}, 'suites': [{
                'name': 'suite', 'codec': 'H.264', 'mainline_decoder': 'decoder', 'test_method': 'md5',
                'vectors': [{'name': 'first', 'input_path': 'resources/first'},
                            {'name': 'second', 'input_path': 'resources/second'}]}]}))
            plan = {'bundle': str(root), 'bundle_sha256': window.sha(manifest), 'suite': 'suite',
                    'kernel': 'mainline', 'start': 0, 'count': 2, 'vector_timeout_seconds': 30}
            calls = []

            def process(command, log, timeout, env):
                calls.append(command)
                if 'list' in command:
                    log.write_text('    decoder: available... OK\n')
                    return 0
                raise subprocess.TimeoutExpired(command, timeout)

            with patch.object(window, 'bounded_process', side_effect=process), \
                    self.assertRaisesRegex(RuntimeError, 'first: Timeout'):
                window.run_fluster(plan, output, window.time.monotonic() + 600, {})
            result = json.loads((output / 'results.json').read_text())
            self.assertEqual(result['vectors']['first']['result'], 'Timeout')
            self.assertEqual(result['vectors']['second']['result'], 'Not run')
            self.assertEqual(len(calls), 2)

    def test_fluster_pixel_failure_continues_but_kernel_warning_stops(self):
        for warning in (False, True):
            with self.subTest(warning=warning), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = root / 'bundle-manifest.json'
                manifest.write_text(json.dumps({'fluster_revision': 'locked', 'files': {}, 'suites': [{
                    'name': 'suite', 'codec': 'H.264', 'mainline_decoder': 'decoder', 'test_method': 'md5',
                    'vectors': [{'name': 'first'}, {'name': 'second'}]}]}))
                plan = {'bundle': str(root), 'bundle_sha256': window.sha(manifest), 'suite': 'suite',
                        'kernel': 'mainline', 'start': 0, 'count': 2, 'vector_timeout_seconds': 30}
                visited = []

                def process(command, log, timeout, env):
                    if 'list' in command:
                        log.write_text('    decoder: available... OK\n')
                        return 0
                    name = command[command.index('-tv') + 1]
                    visited.append(name)
                    status = 'Fail' if name == 'first' else 'Success'
                    Path(command[command.index('-so') + 1]).write_text(json.dumps({
                        'test_suites': {'suite': {'decoders': {'decoder': {'vectors': {
                            name: {'result': status, 'time': 1}}}}}}}))
                    return int(status == 'Fail')

                with patch.object(window, 'bounded_process', side_effect=process), \
                        patch.object(window, 'faulted', return_value=False), \
                        patch.object(window, 'require_clean_kernel_log',
                                     side_effect=RuntimeError('kernel WARNING') if warning else None):
                    if warning:
                        with self.assertRaisesRegex(RuntimeError, 'kernel WARNING'):
                            window.run_fluster(plan, root, window.time.monotonic() + 600, {})
                    else:
                        self.assertFalse(window.run_fluster(plan, root, window.time.monotonic() + 600, {}))
                self.assertEqual(visited, ['first'] if warning else ['first', 'second'])
                result = json.loads((root / 'results.json').read_text())
                self.assertEqual(result['vectors']['first']['result'], 'Fail')
                self.assertEqual(result['vectors']['second']['result'], 'Not run' if warning else 'Success')

    def test_kernel_decoder_timeout_is_not_hidden_by_fluster_error(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window, 'run', return_value=(
                    'Nov 05 10:57:44 Khadas kernel: aml-vdec-drv fe320000.video-codec: dec timeout=500\n')):
            with self.assertRaisesRegex(TimeoutError, 'Kernel decoder timeout'):
                window.require_clean_kernel_log(Path(directory))
            self.assertIn('dec timeout=500', (Path(directory) / 'kernel.log').read_text())

    def test_bounded_process_terminates_decoder_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminated = root / 'child-terminated'
            child = ('import signal,sys; from pathlib import Path; '
                     f'signal.signal(signal.SIGTERM, lambda *_: (Path({str(terminated)!r}).write_text("stopped"), sys.exit(0))); '
                     'print("ready", flush=True); signal.pause()')
            parent = ('import signal,subprocess,sys; '
                      'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                      f'p=subprocess.Popen([sys.executable,"-c",{child!r}],stdout=subprocess.PIPE,text=True); '
                      'assert p.stdout.readline().strip()=="ready"; p.wait()')
            with self.assertRaises(subprocess.TimeoutExpired):
                window.bounded_process([sys.executable, '-c', parent], root / 'process.log', 2)
            self.assertEqual(terminated.read_text(), 'stopped')

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
                for release, flags in [('7.3.0-vim4kvm-vdec5+', ['--at-board']),
                                       (window.BASE_RELEASE, ['--once-baseline', '/baseline.json'])]:
                    proof = {'release': release, 'source': source, 'once': True}
                    manifest.write_text(json.dumps(proof))
                    for action in set(window.ACTIONS) - {'arm-baseline', 'verify-baseline'}:
                        if flags[0] == '--once-baseline' and action in window.BOOT_ACTIONS:
                            continue
                        with self.subTest(source=source, release=release, action=action), \
                                patch.object(sys, 'argv', [str(SOURCE), action, '--execute',
                                                           *flags, '--manifest', str(manifest)]), \
                                patch.object(window.subprocess, 'run') as run, \
                                self.assertRaisesRegex(ValueError, 'Known failing candidate'):
                            window.main()
                        run.assert_not_called()
                for release in ('7.3.0-vim4kvm-vdec3+', '7.3.0-vim4kvm-vdec4+'):
                    for action in ('arm-baseline', 'verify-baseline'):
                        window.require_candidate(action, {'release': release, 'source': source})

    def test_timeout_is_not_retried(self):
        with patch.object(window.subprocess, 'run', side_effect=subprocess.TimeoutExpired('test', 10)) as run, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            window.run('test', timeout=10)
        self.assertEqual(run.call_count, 1)

    def test_once_package_cannot_overwrite_default_boot_files(self):
        proof = {'release': window.BASE_RELEASE, 'once': True, 'source': 'candidate'}
        window.require_candidate('probe', proof, once=True)
        for action in window.BOOT_ACTIONS:
            with self.subTest(action=action), self.assertRaises(ValueError):
                window.require_candidate(action, proof, once=True)
        with self.assertRaises(ValueError):
            window.require_candidate('probe', {'release': window.BASE_RELEASE}, once=True)

    def test_watchdog_requires_runtime_timeout_and_pid_one_ownership(self):
        for timeout, owners, accepted in [('0', '1', False), ('30s', '22', False),
                                          ('30s', '1', True)]:
            with self.subTest(timeout=timeout, owners=owners), \
                    patch.object(window, 'run', side_effect=[timeout, owners]):
                if accepted:
                    window.require_watchdog()
                else:
                    with self.assertRaises(ValueError):
                        window.require_watchdog()

    def test_once_guard_failure_prevents_codec_commands(self):
        args = SimpleNamespace(action='probe', build_id='candidate', once_baseline='/proof')
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_once', side_effect=ValueError('missing watchdog')), \
                patch.object(window, 'run') as run, self.assertRaises(ValueError):
            window.board_window(args)
        run.assert_not_called()

    def test_once_guard_requires_protected_files_private_modules_and_panic(self):
        files = {name: 'expected' for name in
                 (str(window.BOOT_DIR/'Image'), str(window.BOOT_DIR/'vim4.dtb'), '/boot/extlinux/extlinux.conf',
                  '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json')}
        baseline = {'files': files, 'buildIds': ['baseline']}
        trial = '/var/lib/vim4-kvm/display-m1/candidate'
        args = SimpleNamespace(build_id='candidate', once_baseline='/proof')
        for changed_file, mode, panic, accepted in [(False, 'ro', '1', True), (True, 'ro', '1', False),
                                                   (False, 'rw', '1', False), (False, 'ro', '0', False)]:
            content = {'/proof': json.dumps(baseline), '/proc/cmdline': 'init=' + trial + '/init',
                       '/proc/sys/kernel/panic': '20', '/proc/sys/kernel/panic_on_oops': panic,
                       '/proc/self/mountinfo': f'30 1 0:1 {trial}/modules/{window.BASE_RELEASE} '
                       f'/usr/lib/modules/{window.BASE_RELEASE} {mode},relatime - ext4 /dev/root rw'}
            with self.subTest(changed_file=changed_file, mode=mode, panic=panic), \
                    patch.object(window.Path, 'read_text', autospec=True,
                                 side_effect=lambda path: content[str(path)]), \
                    patch.object(window.Path, 'resolve', return_value=Path('/usr/lib/modules', window.BASE_RELEASE)), \
                    patch.object(window, 'sha', side_effect=lambda path:
                                 'changed' if changed_file and path == str(window.BOOT_DIR/'Image') else 'expected'), \
                    patch.object(window.os, 'uname', return_value=SimpleNamespace(release=window.BASE_RELEASE)), \
                    patch.object(window, 'require_watchdog') as watchdog:
                if accepted:
                    window.require_once(args)
                    watchdog.assert_called_once()
                else:
                    with self.assertRaises(ValueError):
                        window.require_once(args)
                    watchdog.assert_not_called()

    def test_no_codec_command_before_baseline_boot_files_are_armed(self):
        args = SimpleNamespace(action='probe', build_id='candidate')
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_baseline_files', side_effect=ValueError('not armed')), \
                patch.object(window, 'run') as run, self.assertRaises(ValueError):
            window.board_window(args)
        run.assert_not_called()

    def test_timeout_quarantines_without_unload_reload_or_service_restart(self):
        args = SimpleNamespace(action='probe', build_id='candidate', fixtures='/fixtures')
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window.Path, 'glob', return_value=[]), \
                patch.object(window.Path, 'write_text') as marker, \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_baseline_files'), \
                patch.object(window, 'begin_stage', return_value={}), \
                patch.object(window, 'finish_stage'), \
                patch.object(window, 'probe_runtime_pm', side_effect=subprocess.TimeoutExpired('metadata open', 8)), \
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

    def test_different_vendor_sample_is_rejected_before_any_hardware_window(self):
        args = SimpleNamespace(action='h264', build_id='candidate', fixtures='/fixtures')
        metadata = {'streams': [{'codec_name': 'h264', 'width': 640, 'height': 368,
                                 'pix_fmt': 'yuv420p', 'nb_read_frames': '600'}]}
        with patch.object(window.os, 'geteuid', return_value=0), \
                patch.object(window.Path, 'exists', return_value=False), \
                patch.object(window, 'build_id', return_value='candidate'), \
                patch.object(window, 'require_baseline_files'), \
                patch.object(window, 'sha', return_value='different sample'), \
                patch.object(window, 'begin_stage') as stage, \
                patch.object(window.subprocess, 'run') as service, \
                patch.object(window, 'run', return_value=json.dumps(metadata)) as run, \
                self.assertRaisesRegex(ValueError, 'identical vendor'):
            window.board_window(args)
        stage.assert_not_called()
        service.assert_not_called()
        self.assertEqual([call.args[0] for call in run.call_args_list], ['ffprobe'])

    def test_unsuspended_close_preserves_recovery_marker_without_unloading(self):
        args = SimpleNamespace(action='probe', build_id='candidate', fixtures='/fixtures')
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
                    patch.object(window, 'probe_runtime_pm', side_effect=lambda: window.require_suspended(device)), \
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
            args = SimpleNamespace(action='compliance', build_id='test')
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            args.action = 'probe'
            state = window.begin_stage(args, path)
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            window.finish_stage(state, True, path)
            with self.assertRaises(ValueError):
                window.begin_stage(args, path)
            args.action = 'compliance'
            state = window.begin_stage(args, path)
            window.finish_stage(state, False, path)
            for action in ('probe', 'compliance', 'h264', 'wave'):
                args.action = action
                with self.subTest(action=action), self.assertRaises(ValueError):
                    window.begin_stage(args, path)

    def test_higher_stages_require_their_immediate_predecessor(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window.Path, 'read_text', return_value='boot-test'):
            path = Path(directory) / 'stages.json'
            path.touch()
            identity = {'boot': 'boot-test', 'build': 'test'}
            for action, previous, passed in [('compliance', 'probe', []),
                                             ('h264', 'compliance', ['probe']),
                                             ('h264-1080p', 'h264', ['probe', 'compliance'])]:
                state = {'identity': identity, 'passed': passed}
                with self.subTest(action=action), patch.object(window.json, 'loads', return_value=state):
                    args = SimpleNamespace(action=action, build_id='test')
                    with self.assertRaisesRegex(ValueError, 'Required previous stage: ' + previous):
                        window.begin_stage(args, path)



if __name__ == '__main__':
    unittest.main()
