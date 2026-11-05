import base64
import contextlib
import http.server
import importlib.machinery
import importlib.util
import json
import io
from pathlib import Path
import shutil
import subprocess
import struct
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
FORMAL_RELEASE = window.once.formal_baseline()['release']


class WindowTests(unittest.TestCase):
    def test_return_reboots_without_kbase_and_checks_restored_identity(self):
        once = window.load('bind_once', ROOT/'packaging/kernel/display-once.py')
        for upload_timeout, missing_after_reboot in ((False, False), (True, False), (False, True)):
            with self.subTest(upload_timeout=upload_timeout, missing_after_reboot=missing_after_reboot), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                note = struct.pack('<III', 4, 20, 3) + b'GNU\0' + b'\xaa'*20
                contents = {'/sys/kernel/notes': note, '/proc/cmdline': b'root=test',
                            '/boot/kernels/'+FORMAL_RELEASE+'/Image': b'baseline kernel',
                            '/boot/kernels/'+FORMAL_RELEASE+'/vim4.dtb': b'baseline dt',
                            '/boot/extlinux/extlinux.conf': ('DEFAULT Mainline\nLABEL Mainline\n LINUX /kernels/'+FORMAL_RELEASE+'/Image\n FDT /kernels/'+FORMAL_RELEASE+'/vim4.dtb\n').encode(),
                            '/etc/vim4-kvm/kernels.json': b'original registry',
                            '/etc/vim4-kvm/runtime-build.json': b'original runtime',
                            '/lib/modules/'+FORMAL_RELEASE+'/wave5.ko': b'baseline module'}
                helpers = ['/usr/libexec/'+name for name in ('vim4-board-runtime', 'vim4-kvm-run',
                                                            'vim4-mainline-prepare', 'vim4-mainline-gadget-prepare')]
                contents.update({name: b'baseline helper' for name in helpers})
                contents.update({'/sys/module/'+name+'/notes/.note.gnu.build-id': note for name in
                                 ('t7_hdmirx', 't7_vdin_test', 'wave5', 'mali_kbase', 'vim4_kbase_heaps', 'governor_vim4')})
                contents.update({'/sys/firmware/devicetree/base/'+name: b'baseline property' for name in
                                 ('model', 'compatible', 'soc/bus@fe000000/gpu@400000/compatible')})
                boot = '/boot/kernels/'+FORMAL_RELEASE
                contents.update({boot+'/'+name: name.encode() for name in ('panfrost.dtb', 'config', 'Module.symvers', 'vmlinux.btf')})
                for name, data in contents.items():
                    path = root/name.lstrip('/')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                names = ('t7_hdmirx', 't7_vdin_test', 'wave5', 'mali_kbase', 'vim4_kbase_heaps', 'governor_vim4')
                manifest = dict(modules={'wave5.ko': once.sha(root/('lib/modules/'+FORMAL_RELEASE+'/wave5.ko'))},
                                files={name: once.sha(root/(boot+'/'+name).lstrip('/')) for name in
                                       ('Image', 'vim4.dtb', 'panfrost.dtb', 'config', 'Module.symvers', 'vmlinux.btf')})
                (root/'manifest.json').write_text(json.dumps(manifest))
                (root/(boot+'/manifest.json').lstrip('/')).write_bytes((root/'manifest.json').read_bytes())
                (root/'sources.toml').write_text(
                    '[tested_build]\nmanifest_path="manifest.json"\nmanifest_sha256='+json.dumps(once.sha(root/'manifest.json'))+'\n[tested_build.module_build_ids]\n'+
                    ''.join(name+'="'+'a'*40+'"\n' for name in names)+
                    '[retained_runtime]\nrelease='+json.dumps(FORMAL_RELEASE)+'\nbuild_id="'+'a'*40+'"\n'+
                    'image_sha256='+json.dumps(once.sha(root/(boot+'/Image').lstrip('/')))+'\n'+
                    'board_dtb_sha256='+json.dumps(once.sha(root/(boot+'/vim4.dtb').lstrip('/')))+'\n')
                def board_path(*parts):
                    path = Path(*parts)
                    return root/str(path).lstrip('/') if str(path).startswith(('/sys/', '/proc/', '/boot/', '/etc/', '/lib/', '/usr/')) else path
                def board_open(name, *args, **kwargs):
                    return open(board_path(name), *args, **kwargs)
                def remote_python(host, script):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        exec(script.replace('pathlib.Path(', 'board_path('),
                             dict(board_path=board_path, open=board_open))
                    result = json.loads(output.getvalue())
                    if 'files' in result:
                        result['files'] = {name.removeprefix(str(root)): value for name, value in result['files'].items()}
                    return json.dumps(result)
                def commands(command, **kwargs):
                    if command[0] == 'systemctl':
                        return subprocess.CompletedProcess(command, 0 if command[-1] == 'one-kvm' else 3)
                    if command[0] == 'scp' and upload_timeout:
                        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                    return subprocess.CompletedProcess(command, 0)
                def reboot(*args, **kwargs):
                    for name in helpers:
                        board_path(name).write_bytes(contents[name])
                    if not missing_after_reboot:
                        board_path('/sys/module/mali_kbase/notes/.note.gnu.build-id').write_bytes(note)
                # The remote script reads real fixture files; changing the
                # visible helper bytes models the candidate's bind overlay.
                with patch.object(window, 'ssh_python', side_effect=remote_python), patch.object(
                        window.subprocess, 'run', side_effect=commands) as run, patch(
                        'platform.release', return_value=FORMAL_RELEASE), patch.object(window.once, 'SOURCES', root/'sources.toml'):
                    files = list(contents.keys())[2:9]
                    proof = window.identity('mock', files, baseline=True)
                    for field in ('LINUX', 'FDT'):
                        config = board_path('/boot/extlinux/extlinux.conf')
                        original = config.read_bytes()
                        config.write_bytes(original.replace((' '+field+' /kernels/'+FORMAL_RELEASE).encode(), (' '+field+' /edge').encode()))
                        with self.assertRaisesRegex(AssertionError, 'default LINUX/FDT'):
                            window.identity('mock', files, baseline=True)
                        config.write_bytes(original)
                    for name in helpers:
                        board_path(name).write_bytes(b'candidate bind-visible helper')
                    self.assertNotEqual(window.identity('mock', list(proof['files']))['files'], proof['files'])
                    # A same-release Panfrost or failed candidate need not load
                    # kbase. Its absence must not block the normal recovery reboot.
                    board_path('/sys/module/mali_kbase/notes/.note.gnu.build-id').unlink()
                    run.reset_mock()
                    window.verify_persistent_files('mock', proof)
                    run.assert_not_called()  # File verification does not query applications.
                    plan = dict(baseline_release=proof['release'], baseline_id=proof['build_id'],
                                baseline_cmdline=proof['cmdline'], baseline_files=proof['files'])
                    with patch.object(once.os, 'geteuid', return_value=0), patch.object(
                            once, 'sha', side_effect=lambda name: once.hashlib.sha256(board_path(name).read_bytes()).hexdigest()):
                        once.retained_preflight(plan, proof)
                    work = root/'logs/bind-return'
                    work.mkdir(parents=True)
                    (work/'baseline-proof.json').write_text(json.dumps(proof))
                    with patch.object(window, 'ROOT', root), patch.object(
                            window, 'require_board', return_value=(Mock(), 'token')), patch.object(
                            window, 'boot', side_effect=reboot) as boot_call, patch.object(window, 'ssh', return_value=''), patch.object(
                            window, 'collect', return_value={'returned': True}), patch.object(
                            sys, 'argv', ['board-window', '--window', 'bind-return', 'return-baseline', '--video-check', 'decode-check']):
                        if missing_after_reboot:
                            with self.assertRaises(FileNotFoundError):
                                window.main()
                        elif upload_timeout:
                            with self.assertRaises(subprocess.TimeoutExpired):
                                window.main()
                        else:
                            window.main()
                    self.assertEqual(boot_call.call_count, 1)
                    upload = [call for call in run.call_args_list if call.args[0][0] == 'scp']
                    if missing_after_reboot:
                        self.assertFalse(upload)
                        self.assertFalse(list(work.glob('return-baseline-*.json')))
                        self.assertFalse((work/'returned-baseline-identity.json').exists())
                        continue
                    self.assertEqual(len(upload), 1)
                    self.assertEqual(upload[0].kwargs['timeout'], 30)
                    returned = window.identity('mock', list(proof['files']))
                    window.verify_baseline(proof, returned)

    def test_515_capture_checks_the_actual_default_kernel_and_dt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = ['/boot/vmlinuz-5.15.test', '/boot/dtb-5.15.test/test.dtb', '/boot/extlinux/extlinux.conf']
            contents = dict.fromkeys(files, b'baseline')
            contents.update({'/sys/kernel/notes': struct.pack('<III',4,20,3)+b'GNU\0'+b'\xaa'*20,
                             '/proc/cmdline': b'root=test'})
            for name,data in contents.items():
                p=root/name.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            def board_path(*parts): return root/str(Path(*parts)).lstrip('/')
            def remote(host,script):
                out=io.StringIO()
                with contextlib.redirect_stdout(out):
                    exec(script.replace('pathlib.Path(', 'board_path('),
                         dict(board_path=board_path,open=lambda n,*a,**kw:open(board_path(n),*a,**kw)))
                return out.getvalue()
            config=board_path('/boot/extlinux/extlinux.conf')
            text='DEFAULT Vendor\nLABEL Vendor\n LINUX /vmlinuz-5.15.test\n FDT /dtb-5.15.test/test.dtb\n'
            with patch.object(window,'ssh_python',side_effect=remote), patch('platform.release',return_value='5.15.test'):
                config.write_text(text)
                self.assertEqual(window.identity('mock',files,baseline=True)['release'],'5.15.test')
                config.write_text(text.replace('FDT /dtb-5.15.test/test.dtb','FDTDIR /dtb-5.15.test'))
                self.assertEqual(window.identity('mock',files,baseline=True)['release'],'5.15.test')
                for original in ('/vmlinuz-5.15.test','/dtb-5.15.test/test.dtb'):
                    config.write_text(text.replace(original,'/wrong'))
                    with self.assertRaisesRegex(AssertionError,'default'):
                        window.identity('mock',files,baseline=True)

    def test_formal_return_requires_video_check_before_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'logs/video-required';work.mkdir(parents=True)
            (work/'baseline-proof.json').write_text(json.dumps(dict(release=FORMAL_RELEASE)))
            with patch.object(window,'ROOT',root), patch.object(window,'require_board'), \
                    patch.object(window,'boot') as boot, patch.object(window,'ssh_python') as ssh, \
                    patch.object(sys,'argv',['board-window','--window','video-required','return-baseline']):
                with self.assertRaisesRegex(ValueError,'--video-check'):window.main()
            boot.assert_not_called();ssh.assert_not_called()

    def test_formal_proof_checks_complete_modules_and_loaded_identities(self):
        lock = window.tomllib.loads((ROOT/'packaging/kernel/sources.toml').read_text())
        retained = lock['retained_runtime']
        manifest = json.loads((window.once.SOURCES.parent/lock['tested_build']['manifest_path']).read_text())
        prefix = '/lib/modules/'+retained['release']+'/'
        files = {prefix+name: value for name, value in manifest['modules'].items()}
        boot = '/boot/kernels/'+retained['release']
        files.update({boot+'/'+name: manifest['files'][name] for name in
                      ('Image', 'vim4.dtb', 'panfrost.dtb', 'config', 'Module.symvers', 'vmlinux.btf')})
        files[boot+'/manifest.json'] = lock['tested_build']['manifest_sha256']
        ids = {name: lock['tested_build']['module_build_ids'][name] for name in
               ('t7_hdmirx', 't7_vdin_test', 'wave5', 'mali_kbase', 'vim4_kbase_heaps', 'governor_vim4')}
        proof = dict(release=retained['release'], build_id=retained['build_id'], files=files, loaded_modules=ids)
        def check(value):
            with patch.object(window, 'ssh_python', return_value=json.dumps(value)):
                return window.identity('mock', list(files), baseline=True)
        self.assertEqual(check(proof), proof)
        for name in (boot+'/Image', boot+'/config', prefix+'modules.dep', prefix+next(n for n in manifest['modules'] if n.endswith('.ko.xz'))):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'formal baseline differs'):
                check(dict(proof, files=dict(files, **{name:'bad'})))
        for invalid in (dict(proof, loaded_modules=dict(ids, wave5='wrong')),
                        dict(proof, loaded_modules={}), dict(proof, build_id='0'*40),
                        dict(proof, files=dict(files, **{prefix+'extra/stray.ko':'bad'})),
                        dict(proof, files={n:v for n,v in files.items() if n!=prefix+'modules.dep'})):
            with self.assertRaises(ValueError): check(invalid)

    def test_complete_proof_is_streamed_without_exec_argument_limit(self):
        script = 'proof = ' + repr({'module-'+str(i): 'a'*64 for i in range(2400)})
        self.assertGreater(len(script), 128*1024)
        with patch.object(window.subprocess, 'check_output', return_value='done') as run:
            self.assertEqual(window.ssh_python('mock', script), 'done')
        self.assertEqual(run.call_args.kwargs['input'], script)
        self.assertLess(sum(map(len, run.call_args.args[0])), 1024)
        with patch.object(window, 'ssh_python', return_value='{"release":"candidate"}') as ssh:
            window.identity('mock', ['/boot/kernels/'+FORMAL_RELEASE+'/Image'])
        compile(ssh.call_args.args[1], '<remote baseline identity>', 'exec')

    def test_formal_proof_roundtrip_checks_loaded_modules_gpu_and_application(self):
        proof = dict(release=FORMAL_RELEASE, build_id='a'*40,
                     cmdline='root=test reboot_mode=normal', files={'Image': 'hash'},
                     loaded_modules={'wave5': 'overlay', 'mali_kbase': 'gpu'},
                     applications=['one-kvm'], dt_properties={'model': '00'})
        self.assertIsInstance(window.verify_baseline(proof, dict(proof)), dict)
        for key in ('build_id', 'files', 'loaded_modules', 'applications', 'dt_properties'):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                window.verify_baseline(proof, dict(proof, **{key: 'wrong'}))
        with tempfile.TemporaryDirectory() as directory:
            cache = window.BaselineCache(Path(directory) / 'cache.json')
            self.assertFalse(cache.get(proof, lambda: {'fps': 60})['reused'])
            self.assertTrue(cache.get(proof, lambda: self.fail('must reuse'))['reused'])
            for release in ('7.3.0-vim4kvm-uhd7+', FORMAL_RELEASE+'other'):
                with self.subTest(release=release), self.assertRaises(ValueError):
                    cache.get(dict(proof, release=release), lambda: self.fail('unsupported baseline'))

    def test_same_image_candidate_requires_live_dt_property_identity(self):
        plan = dict(build_id='a'*40, baseline_id='a'*40)
        with self.assertRaisesRegex(ValueError, 'readable DT'):
            window.verify_candidate_dt('unused', plan)
        plan['dt_properties'] = {'soc/display/status': '6f6b617900'}
        plan['baseline_dt_properties'] = {'soc/display/status': '64697361626c656400'}
        with patch.object(window, 'ssh', return_value='6f6b617900\n'):
            window.verify_candidate_dt('unused', plan)
        with patch.object(window, 'ssh', return_value='64697361626c656400\n'):
            with self.assertRaisesRegex(RuntimeError, 'DT property differs'):
                window.verify_candidate_dt('unused', plan)
        with self.assertRaisesRegex(ValueError, 'DT identity must differ'):
            window.verify_candidate_dt('unused', plan, plan['dt_properties'])

    def test_formal_retained_proof_and_existing_module_tree_are_preserved(self):
        once = window.load('formal_once', ROOT / 'packaging/kernel/display-once.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / 'modules' / FORMAL_RELEASE
            modules.mkdir(parents=True)
            (modules / 'wave5.ko.xz').write_bytes(b'qualified overlay')
            proof = dict(release=modules.name, build_id='a'*40, cmdline='root=test',
                         files={str(modules/'wave5.ko.xz'): once.sha(modules/'wave5.ko.xz')})
            plan = dict(release=modules.name, build_id='b'*40, baseline_id=proof['build_id'],
                        baseline_release=proof['release'], baseline_cmdline=proof['cmdline'],
                        baseline_files=proof['files'])
            with patch.object(once.os, 'geteuid', return_value=0), patch.object(
                    once.os, 'uname', return_value=type('Kernel', (), {'release': modules.name})()), patch.object(
                    once, 'MODULE_ROOT', modules.parent), patch.object(once, 'ROOT', root / 'display-m1'):
                once.retained_preflight(plan, proof)
                once.cleanup_module_mountpoint(plan)
                with self.assertRaises(RuntimeError):
                    once.retained_preflight(dict(plan, baseline_id='c'*40), proof)
                (modules / 'wave5.ko.xz').write_bytes(b'wrong')
                with self.assertRaisesRegex(RuntimeError, 'file changed'):
                    once.retained_preflight(plan, proof)

    def test_baseline_reboot_reason_does_not_relax_other_identity(self):
        before = dict(release='5.15.test', build_id='a'*40, files={'/boot/Image':'hash'},
                      cmdline='root=PARTUUID=abcd reboot_mode=watchdog_reboot rw')
        after = dict(before, cmdline='root=PARTUUID=abcd reboot_mode=normal rw')
        window.verify_baseline(before, after)
        unchanged = dict(before, cmdline='root=PARTUUID=abcd reboot_mode=cold_boot rw')
        window.verify_baseline(unchanged, unchanged)
        invalid = [dict(after, build_id='b'*40), dict(after, files={}),
                   dict(after, release='7.3.test'),
                   dict(after, cmdline=after['cmdline']+' init=/other'),
                   dict(after, cmdline=after['cmdline']+' reboot_mode=normal'),
                   dict(after, cmdline=after['cmdline'].replace('normal','unknown'))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                window.verify_baseline(before, value)

    def test_cleanup_ignores_observations_and_fits_linux_exec_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / 'cleanup.py'
            module.write_text('def cleanup_module_mountpoint(plan):\n    print(plan["release"], plan.get("payload_id", "legacy"))\n')
            legacy = dict(build_id='1' * 40, release='7.3.0-vim4kvm-uhd4+',
                          files={str(i): 'a' * 64 for i in range(4000)})
            current = dict(legacy, namespace='kbase', payload_id='default')
            for plan in (legacy, current):
                window.record_candidate(root, plan, 'a' * 64)
            for name, data in (('candidate-manager-proof.json', {}),
                               ('candidate-running-identity.json', {'release': FORMAL_RELEASE}),
                               ('candidate-receiver-ready.json', {'framesDecoded': 12})):
                (root / name).write_text(json.dumps(data))
            script = window.module_cleanup_script(window.recorded_candidates(root), str(module))
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
            recovered = window.recorded_candidates(root)
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

    def test_autoboot_prompt_with_dropped_leading_bytes_is_interrupted(self):
        uart = Mock()
        uart.open_port.return_value = 42
        # Observed on VIM4: only the prompt's tail survived the UART read.
        chunks = [b'Set reboot_mode to watchdog reboot\r\nautoboot\r\n', b'kvim4#', b'login:']
        process = Mock()
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(window, 'load', return_value=uart), \
                patch.object(window, 'ssh', side_effect=['old-boot', 'c8:63:14:74:70:0d']), \
                patch.object(window.subprocess, 'Popen', return_value=process), \
                patch.object(window.select, 'select', return_value=([42], [], [])), \
                patch.object(window.os, 'read', side_effect=chunks), \
                patch.object(window.os, 'write') as write, \
                patch.object(window.os, 'close'), patch.object(window, 'ready'):
            window.boot('mock', 'serial', Path(directory), dict(command='sysboot candidate', release='candidate'))
        self.assertEqual(write.call_args_list[0].args[1], b' ')

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
        once = window.load('payload_stage', ROOT / 'packaging/kernel/display-once.py')
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
            (root / 'module-mounts').mkdir()
            with patch.object(once, 'ROOT', root / 'display-m1'), patch.object(once, 'MODULE_ROOT', root / 'module-mounts'), patch.object(once.os, 'geteuid', return_value=0):
                once.stage(bundle, retained_baseline=proof)
                with self.assertRaises(FileExistsError):
                    once.stage(bundle, retained_baseline=proof)
                once.stage(bundle, retained_baseline=proof, reuse_staged=True)
                image = candidate / 'Image'
                image.chmod(0o644)
                image.write_bytes(b'changed kernel')
                image.chmod(0o444)
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    once.stage(bundle, retained_baseline=proof, reuse_staged=True)
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
        once = window.load('trial_gate', ROOT / 'packaging/kernel/display-once.py')
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
            configured = dict(proof, measurement={'settings': {'codec': 'h264', 'source': 'm6'}})
            self.assertFalse(cache.get(configured, measure, '2026-10-31')['reused'])
            self.assertTrue(cache.get(configured, measure, '2026-10-31')['reused'])
            configured['measurement']['settings']['codec'] = 'h265'
            self.assertFalse(cache.get(configured, measure, '2026-10-31')['reused'])
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
clock=0;
const early=await measureDecoded(async()=>({id:'v',ssrc:1,framesDecoded:1+clock/50}),10,
 {...options,shouldStop:()=>clock>=200});
assert.equal(early.elapsedMs,200);
assert.equal(early.fps,20);
assert.equal(result.elapsedMs,200);
assert.equal(result.samples[0].framesDecoded,1);
assert.equal(result.samples.length,5);
clock=0;
await assert.rejects(measureDecoded(async()=>({framesDecoded:0}),.2,options),/No actual decoded/);
clock=0;
await assert.rejects(measureDecoded(async()=>({id:'v',ssrc:clock?2:1,framesDecoded:1}),.2,options),/stream changed/);
'''
        subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True, timeout=10)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for receiver transport replay')
    def test_video_transport_has_no_audio_or_hid_and_closes_session(self):
        script = r'''
import assert from 'node:assert/strict';
import {connectVideo,closeVideo} from './tools/board-window-timing.mjs';
const requests=[], tracks=[];
globalThis.window={};
globalThis.document={querySelector:()=>({})};
globalThis.MediaStream=class {};
globalThis.RTCPeerConnection=class {
  iceGatheringState='complete';
  localDescription={sdp:'v=0'};
  addTransceiver(...args){tracks.push(args);}
  async createOffer(){return {};}
  async setLocalDescription(){}
  async setRemoteDescription(answer){assert.equal(answer.sdp,'answer');}
  close(){this.closed=true;}
};
globalThis.fetch=async (url,options)=>{
  requests.push([url,JSON.parse(options.body)]);
  return {ok:true,json:async()=>({session_id:'test-session',sdp:'answer'})};
};
const page={route:async()=>{},goto:async()=>{},evaluate:async(fn,arg)=>fn(arg)};
await connectVideo(page,'http://example.test',undefined);
assert.deepEqual(tracks,[['video',{direction:'recvonly'}]]);
await closeVideo(page);
assert.equal(window.boardPeers[0].closed,true);
assert.deepEqual(requests.map(r=>r[0]),['/api/webrtc/offer','/api/webrtc/close']);
assert.deepEqual(requests[1][1],{session_id:'test-session'});
'''
        subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
