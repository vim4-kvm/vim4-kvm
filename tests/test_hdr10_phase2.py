import importlib.util
import ctypes
import fcntl
import io
import json
from pathlib import Path
import tarfile
import tempfile
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from test_display_once import static_elf

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'packaging/hdr10' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gates, pack = load('m6-gates'), load('assemble-phase2')
window = load('phase2-window')
inspect = load('analyze-phase2')
board = load('phase2-board')
factories = load('check-phase2-plugins')
SCREENS = json.loads((ROOT / 'tests/fixtures/m6-hdr-gates.json').read_text())


def held_queue():
    queue=Mock()
    queue.read.return_value=dict(state='held',heavy=False,started=time.time(),seconds=1800)
    return queue


class M6Tests(unittest.TestCase):
    def test_observed_combined_chrome_menu_qualifies_without_hid(self):
        screen = dict(SCREENS['chrome'], items=[dict(
            text='• Chrome File Edit View History Bookmarks',
            x=-0.294, y=2.679, w=393.937, h=27.421)])
        client = Mock()
        control = gates.M6(client, lambda: False, '/unused',
                           Path(tempfile.gettempdir()) / 'm6-merged')
        control.screen = Mock(return_value=screen)
        control.qualify(False)
        client.call.assert_not_called()
        self.assertFalse(control.restore_needed)
        for text in ('Safari Chrome File Edit View', 'Chrome webpage'):
            screen['items'][0]['text'] = text
            with self.assertRaises(gates.GateError): control.qualify(False)
        client.call.assert_not_called()

    def controller(self, screens):
        client = Mock()
        state = [False]
        controller = gates.M6(client, lambda: state[0], '/unused', Path(tempfile.gettempdir()) / 'm6-unit')
        controller.screen = Mock(side_effect=[SCREENS['chrome'],*[SCREENS[name] for name in screens]])
        controller.qualify(False)
        def call(name, args=None):
            if name == 'mouse_move': client.point = args['coordinate']
            if name == 'left_click' and client.point[0] > 1600: state[0] = not state[0]
        client.call.side_effect = call
        return controller, client, state

    def test_real_ocr_foreground_general_selection_toggle_and_close(self):
        control, client, state = self.controller(['general','off','off','off','on','on','chrome'])
        control.toggle(True)
        self.assertTrue(state[0])
        control.close()
        points = [c.args[1]['coordinate'] for c in client.call.call_args_list if c.args[0] == 'mouse_move']
        self.assertEqual(len(points), 3)
        self.assertTrue(1688 < points[1][0] < 1720 and 533 < points[1][1] < 552)
        self.assertTrue(1030 < points[2][0] < 1048 and 193 < points[2][1] < 208)

    def test_restore_reobserves_moved_hdr_row(self):
        control, client, state = self.controller(['on','on','on','off','off','chrome'])
        control.click((1704,540))
        control.restore()
        self.assertFalse(state[0])
        points = [c.args[1]['coordinate'] for c in client.call.call_args_list if c.args[0] == 'mouse_move']
        self.assertTrue(570 < points[1][1] < 590)

    def test_chrome_cannot_pass_settings_scroll_gate(self):
        with self.assertRaises(gates.GateError): gates.settings(SCREENS['chrome'])
        control, client, state = self.controller(['off','chrome'])
        with self.assertRaises(gates.GateError): control.toggle(True)
        client.call.assert_not_called()
        self.assertFalse(state[0])

    def test_hid_error_is_not_replayed(self):
        control, client, state = self.controller(['off','off','off'])
        client.call.side_effect = RuntimeError('MCP action outcome unknown')
        with self.assertRaises(RuntimeError): control.toggle(True)
        self.assertEqual(client.call.call_count, 1)
        self.assertTrue(control.restore_needed)
        client.call.side_effect=None
        control.screen=Mock(return_value=SCREENS['chrome'])
        control.restore()
        self.assertFalse(control.restore_needed)
        self.assertEqual(client.call.call_count,1)

    def test_failed_menu_launch_recovers_open_apple_menu_without_replay(self):
        menu=dict(SCREENS['chrome'],items=[*SCREENS['chrome']['items'],
            dict(text='• About This Mac',x=20,y=40,w=120,h=20)])
        control,client,_=self.controller([])
        control.hid('mouse_move',{'coordinate':[27,13]})
        control.screen=Mock(side_effect=[menu,menu,SCREENS['chrome'],SCREENS['chrome']])
        control.restore()
        self.assertEqual(client.call.call_count,2)
        self.assertEqual(client.call.call_args.args,('key',{'text':'Escape'}))

    def test_menu_animation_is_observed_without_replaying_click(self):
        menu=dict(SCREENS['chrome'],items=[*SCREENS['chrome']['items'],
            dict(text='• System Settings...',x=22,y=75,w=150,h=20)])
        control,client,_=self.controller([])
        unpainted=dict(SCREENS['general'],items=[dict(text='System Settings Edit View Window Help',x=45,y=6,w=300,h=20)])
        control.screen=Mock(side_effect=[SCREENS['chrome'],SCREENS['chrome'],menu,unpainted,SCREENS['general']])
        control.displays=Mock()
        with patch.object(gates.time,'sleep'):
            control.open()
        clicks=[c for c in client.call.call_args_list if c.args[0]=='left_click']
        self.assertEqual(len(clicks),2)
        control.displays.assert_called_once_with(SCREENS['general'])

    def test_visible_menu_from_stopped_preparation_is_reused(self):
        menu=dict(SCREENS['chrome'],items=[*SCREENS['chrome']['items'],
            dict(text='• System Settings...',x=22,y=75,w=150,h=20)])
        control,client,_=self.controller([])
        control.screen=Mock(side_effect=[menu,SCREENS['general']])
        control.displays=Mock()
        control.open()
        points=[c.args[1]['coordinate'] for c in client.call.call_args_list if c.args[0]=='mouse_move']
        self.assertEqual(points,[[97,85]])

    def test_unqualified_restore_does_not_touch_existing_hdr_or_foreground(self):
        client=Mock()
        control=gates.M6(client,lambda:True,'/unused',Path(tempfile.gettempdir())/'m6-unqualified')
        control.screen=Mock(side_effect=AssertionError('restore must not observe or act'))
        control.restore()
        client.call.assert_not_called()
        self.assertFalse(control.restore_needed)

    def test_preexisting_settings_is_rejected_without_close_or_hdr_change(self):
        client=Mock()
        control=gates.M6(client,lambda:False,'/unused',Path(tempfile.gettempdir())/'m6-settings')
        control.screen=Mock(return_value=SCREENS['general'])
        with self.assertRaises(gates.GateError):control.qualify(False)
        control.restore()
        client.call.assert_not_called()


def archive(path, files):
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name); info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


class AssemblyTests(unittest.TestCase):
    def fixture(self, root, without_jpeg=False):
        release = '7.3.0-vim4kvm-uhd5+'
        module_files = {release + '/kernel/xt_DSCP.ko':b'upper', release + '/kernel/xt_dscp.ko':b'lower'}
        mod = root/'modules.tar.gz'; archive(mod, module_files)
        base = {'Image':b'image', 'vim4.dtb':b'kbase-dt', 'panfrost.dtb':b'panfrost-dt', 'modules.tar.gz':mod.read_bytes(),
                'runtime/usr/libexec/vim4-kvm-run':b'old launcher',
                'runtime/gstreamer-1.0/old.so':b'old plugin','runtime/one-kvm':b'old app'}
        report = dict(source='a'*40, release=release, kernel_build_id='1'*40,
            modules={name.split('/',1)[1]:pack.digest(data) for name,data in module_files.items()},
            files={name:pack.digest(data) for name,data in base.items()})
        base['manifest.json'] = json.dumps(report).encode()
        kernel = root/'kernel.tar.gz'; archive(kernel, base)
        data = {name:b'elf fixture' for name in ('one-kvm','nanokvm','jetkvm','ustreamer','libjanus_ustreamer.so')}
        data.update({'gstreamer-1.0/'+name:b'plugin fixture' for name in set(factories.PRIVATE.values())})
        if without_jpeg: del data['gstreamer-1.0/libgstvim4jpegenc.so']
        data['manifest.json'] = json.dumps(dict(sha256={n:pack.digest(d) for n,d in data.items()})).encode()
        user = root/'user.tar.gz'; archive(user, data)
        baseline = root/'baseline.json'; baseline.write_text(json.dumps(dict(cmdline='root=PARTUUID=12345678-02 rw')))
        return SimpleNamespace(kernel=kernel,kernel_sha256=pack.once.sha(kernel),userspace=user,userspace_sha256=pack.once.sha(user),
            baseline=baseline,output=root/'payload.tar.gz',gpu='panfrost',payload_id='unit-dry',dry_run=True)

    def test_dryrun_preserves_case_distinct_modules_and_static_init_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp))
            def cc(command, **kwargs):
                bindings=(Path(next(s[2:] for s in command if s.startswith('-I')))/'phase2-bindings.h').read_text()
                self.assertNotIn('"/gstreamer-1.0/',bindings)
                self.assertNotIn('"/one-kvm"',bindings)
                root=next(s.split('=',1)[1].strip('"') for s in command if s.startswith('-DTRIAL_ROOT='))
                Path(command[-1]).write_bytes(static_elf()+root.encode()+b'\0')
            with patch.object(pack.subprocess, 'run', side_effect=cc), \
                 patch.object(pack,'verify_plugins',return_value={'offline_fixture':True}): pack.assemble(args)
            with tarfile.open(args.output) as tar:
                plan,_,entries=pack.once.read_trial(tar)
                self.assertIn('modules/7.3.0-vim4kvm-uhd5+/kernel/xt_DSCP.ko',entries)
                self.assertIn('modules/7.3.0-vim4kvm-uhd5+/kernel/xt_dscp.ko',entries)
                self.assertEqual(plan['build_id'],'1'*40)
                self.assertTrue(json.load(tar.extractfile('manifest.json'))['dry_run'])
                self.assertIn('runtime/gstreamer-1.0/libgstvim4jpegenc.so',entries)
                self.assertIn('runtime/check-phase2-plugins.py',entries)

    def test_wrong_source_hash_and_uhd5_board_mode_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp)); args.kernel_sha256='0'*64
            with self.assertRaisesRegex(ValueError,'SHA mismatch'): pack.assemble(args)
            args.kernel_sha256=pack.once.sha(args.kernel); args.dry_run=False
            with self.assertRaisesRegex(ValueError,'dry-run only'): pack.assemble(args)
            self.assertFalse(args.output.exists())

    def test_missing_jpeg_rejected_before_compilation_or_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp),without_jpeg=True)
            with patch.object(pack,'verify_plugins') as check:
                with self.assertRaisesRegex(ValueError,'vim4jpegenc'): pack.assemble(args)
                check.assert_not_called()
            self.assertFalse(args.output.exists())

    def test_system_jpeg_factory_cannot_mask_an_incomplete_private_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for name in set(factories.PRIVATE.values()): (root/name).write_bytes(b'fixture')
            def inspect(command,**kwargs):
                name=command[-1]
                path=(Path('/baseline') if name=='vim4jpegenc' else root)/factories.PRIVATE[name]
                return SimpleNamespace(returncode=0,stdout='  Filename '+str(path)+'\n',stderr='')
            with patch.object(factories.subprocess,'run',side_effect=inspect):
                with self.assertRaisesRegex(ValueError,'outside.*vim4jpegenc'): factories.check(root)


class WindowTests(unittest.TestCase):
    def test_uhd5_cannot_take_board_ticket(self):
        args=SimpleNamespace(observer=Path('/bin/sh'))
        fixture={g:dict(manifest=dict(gpu=g,dry_run=True)) for g in ('panfrost','kbase')}
        for g in fixture:
            setattr(args,g,Path('unused'));setattr(args,g+'_sha256','0'*64)
        with patch.object(window,'payload',side_effect=lambda path,sha:fixture['panfrost'] if path==Path('pan') else fixture['kbase']):
            args.panfrost=Path('pan')
            with self.assertRaisesRegex(ValueError,'no tested uhd6'):
                window.preflight(args,dict(tested_build=dict(release='7.3.0-vim4kvm-uhd5+')))

    def test_workload_and_collection_failures_still_restore_and_release_sampling(self):
        events=[]
        with tempfile.TemporaryDirectory() as tmp:
            runner=object.__new__(window.Window)
            runner.args=SimpleNamespace(window='unit',observer=Path('/bin/true'),device='unused',
                baseline_files=Path(tmp)/'baseline.json',panfrost=Path('pan'),panfrost_sha256='0'*64)
            runner.args.baseline_files.write_text('[]')
            runner.output=Path(tmp);runner.remote='/var/tmp/unit';runner.failures=[]
            runner.operations=threading.Lock();runner.deadline=time.monotonic()+1440
            runner.api=Mock(return_value={})
            def board(operation,*args,**kwargs):
                events.append(operation)
                if operation=='status':return '{"taint":0,"cma":{"CmaFree":100}}'
                if operation=='configure':raise RuntimeError('injected workload failure')
            runner.board=board
            runner.recovery_board=board
            def cli(*args,**kwargs):
                events.append(args[0])
                if args[0]=='collect':raise RuntimeError('injected collection failure')
            runner.cli=cli
            runner.recovery_cli=cli
            queue=held_queue();tunnel=Mock();tunnel.poll.return_value=None
            runner.open_tunnel=Mock(return_value=tunnel)
            client=Mock();client.idle.return_value=dict(idle=True)
            m6=Mock();m6.restore_needed=False
            m6.toggle.side_effect=lambda *args:setattr(m6,'restore_needed',True)
            def restored():
                events.append('m6-restored');m6.restore_needed=False
            m6.restore.side_effect=restored
            with patch.object(window.w,'require_board',return_value=(queue,'token')), \
                 patch.object(window.w,'ssh',return_value='{"api_key":"unit"}'), \
                 patch.object(window.w,'MCP',return_value=client), \
                 patch.object(window.w,'source_hdr',return_value=False), \
                 patch.object(window.g,'M6',return_value=m6), \
                 patch.object(window.subprocess,'Popen',return_value=tunnel), \
                 patch.object(window.subprocess,'run') as cleanup, \
                 patch.object(window.threading,'Event'), \
                 patch.object(window.threading,'Thread'):
                with self.assertRaisesRegex(RuntimeError,'Recovery incomplete.*collection'):
                    runner.run()
            self.assertLess(events.index('collect'),events.index('return-baseline'))
            self.assertLess(events.index('return-baseline'),events.index('restore'))
            self.assertLess(events.index('restore'),events.index('m6-restored'))
            self.assertEqual(queue.sampling.call_args_list[-1].args,('token',True))
            self.assertEqual(cleanup.call_args.args[0][-4:],['sampling','--ticket','token','off'])
            self.assertEqual(cleanup.call_args.kwargs['timeout'],window.RECOVERY_SECONDS['sampling'])
            tunnel.terminate.assert_called_once()
            self.assertEqual(runner.open_tunnel.call_count,3)

    def test_initial_rejections_and_pre_hid_failure_never_take_m6_restore_ownership(self):
        for cause in ('hdr-on','not-idle','save-failure'):
            with self.subTest(cause=cause),tempfile.TemporaryDirectory() as tmp:
                with patch.object(window,'REPO',Path(tmp)):
                    runner=window.Window(SimpleNamespace(window='rejected',observer=Path('/bin/true'),device='unused'))
                runner.api=Mock(return_value={});runner.open_tunnel=Mock(return_value=Mock())
                runner.cli=Mock();runner.recovery_cli=Mock()
                runner.board=Mock(side_effect=RuntimeError('save failure'))
                client=Mock();client.idle.return_value=dict(idle=cause!='not-idle')
                m6=Mock();m6.restore_needed=False
                with patch.object(window.w,'require_board',return_value=(held_queue(),'token')), \
                     patch.object(window.w,'ssh',return_value='{"api_key":"unit"}'), \
                     patch.object(window.w,'MCP',return_value=client), \
                     patch.object(window.w,'source_hdr',return_value=cause=='hdr-on'), \
                     patch.object(window.subprocess,'run'), \
                     patch.object(window.g,'M6',return_value=m6):
                    with self.assertRaises(RuntimeError):runner.run()
                m6.toggle.assert_not_called();m6.restore.assert_not_called()
                client.call.assert_not_called()
                if cause!='save-failure':runner.board.assert_not_called()

    def test_reboot_replaces_alive_but_stale_forwarder_before_readiness(self):
        runner=object.__new__(window.Window)
        runner.require_work=Mock();runner.require_lease=Mock()
        previous=Mock();current=Mock()
        runner.api=Mock(return_value={})
        with patch.object(window.subprocess,'Popen',return_value=current) as start:
            self.assertIs(runner.open_tunnel(previous),current)
        previous.terminate.assert_called_once()
        previous.wait.assert_called_once_with(timeout=10)
        start.assert_called_once()
        runner.api.assert_called_once_with('vim4/video')

    def test_official_uu_busy_client_is_not_taken_over(self):
        with patch.object(window.subprocess,'check_output',return_value='{"success":true,"data":{"hasActiveConnections":true}}') as call:
            with self.assertRaisesRegex(ValueError,'busy'):
                window.uu_device(Path('/bin/sh'))
            self.assertEqual(call.call_count,1)

    def test_official_uu_other_online_device_is_not_connected(self):
        runner=object.__new__(window.Window);runner.args=SimpleNamespace(uu_device_id='requested')
        runner.api=Mock(return_value={'status':{'device_id':'different'}});runner.command=Mock()
        with self.assertRaisesRegex(RuntimeError,'does not belong'):runner.uu('panfrost')
        runner.command.assert_not_called()

    def test_initial_monitor_read_failure_blocks_workload(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)):
            runner=window.Window(SimpleNamespace(window='monitor-failure'))
            runner.recovery_board=Mock()
            with patch.object(window.w,'ssh',side_effect=RuntimeError('SSH unavailable')):
                runner.watch(Mock())
            self.assertRegex(runner.failures[0],'initial monitor read failed.*SSH unavailable')
            runner.recovery_board.assert_called_once_with('stop',reserve_after=window.REQUIRED_RECOVERY_SECONDS)
            with patch.object(window.subprocess,'Popen') as start:
                with self.assertRaisesRegex(RuntimeError,'monitor rejected workload'):
                    runner.command(['never-executed'])
            start.assert_not_called()

    def test_kbase_allows_only_the_formally_expected_external_module_taint(self):
        for taint in (4096,4096|512,0):
            with self.subTest(taint=taint),tempfile.TemporaryDirectory() as tmp, \
                 patch.object(window,'REPO',Path(tmp)):
                runner=window.Window(SimpleNamespace(window='taint'));runner.expected_taint=4096
                runner.halt=Mock();done=Mock();done.wait.return_value=True
                with patch.object(window.w,'ssh',side_effect=['boot complete',str(taint)]):runner.watch(done)
                if taint==4096:runner.halt.assert_not_called()
                else:runner.halt.assert_called_once_with('boot fault/taint',None)

    def test_fault_deadline_and_lease_reject_all_work_before_remote_dispatch(self):
        for reason in ('fault','deadline','expired','short-lease'):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as tmp, \
                 patch.object(window,'REPO',Path(tmp)):
                runner=window.Window(SimpleNamespace(window='guards',device='unused'))
                queue=held_queue()
                if reason=='fault':runner.failures.append('kernel fault')
                elif reason=='deadline':runner.deadline=time.monotonic()-1
                elif reason=='expired':queue.read.return_value['state']='expired'
                else:queue.read.return_value['seconds']=370
                with patch.object(window.w,'require_board',return_value=(queue,'token')), \
                     patch.object(window.w,'ssh') as remote,patch.object(window.subprocess,'Popen') as process, \
                     patch.object(window.subprocess,'run') as cli:
                    for operation in ('save','configure','plugins','metadata','stop','status'):
                        with self.assertRaises(RuntimeError):runner.board(operation)
                    with self.assertRaises(RuntimeError):runner.work_ssh('upload checkpoint')
                    with self.assertRaises(RuntimeError):runner.cli('boot-candidate','payload')
                    with self.assertRaises(RuntimeError):runner.command(['receiver'],timeout=65)
                    client=Mock()
                    with self.assertRaises(RuntimeError):runner.screenshot(client,Path(tmp)/'screen.jpg')
                    remote.assert_not_called();process.assert_not_called();cli.assert_not_called()
                    client.screenshot.assert_not_called()

    def test_inflight_configure_finishes_before_fault_stop_and_no_configure_can_restart(self):
        entered=threading.Event();release=threading.Event();cancelled=threading.Event();events=[]
        class Failures(list):
            def append(self,value):
                super().append(value);cancelled.set()
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)):
            runner=window.Window(SimpleNamespace(window='ordered-stop'));runner.failures=Failures()
            def ssh(host,command,**kwargs):
                if ' configure ' in command:
                    events.append('configure-start');entered.set()
                    if not release.wait(5):raise RuntimeError('test failed to release configure')
                    events.append('configure-end')
                else:events.append('stop')
                return '{}'
            with patch.object(window.w,'require_board',return_value=(held_queue(),'token')), \
                 patch.object(window.w,'ssh',side_effect=ssh) as remote,ThreadPoolExecutor(2) as workers:
                configure=workers.submit(runner.board,'configure','--app','onekvm')
                self.assertTrue(entered.wait(5))
                fault=workers.submit(runner.halt,'kernel fault/taint')
                self.assertTrue(cancelled.wait(5));release.set()
                configure.result(5);fault.result(5)
                with self.assertRaisesRegex(RuntimeError,'monitor rejected'):
                    runner.board('configure','--app','nanokvm')
                self.assertEqual(events,['configure-start','configure-end','stop'])
                self.assertEqual(remote.call_count,2)

    def test_recovery_is_restricted_and_does_not_clear_work_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(window,'REPO',Path(tmp)):
            runner=window.Window(SimpleNamespace(window='recovery',device='unused'))
            runner.failures.append('kernel fault');runner.deadline=0
            with patch.object(window.w,'require_board',return_value=(held_queue(),'token')), \
                 patch.object(window.w,'ssh',return_value='{}') as remote, \
                 patch.object(window.subprocess,'run') as cli:
                runner.recovery_board('stop');runner.recovery_board('restore')
                runner.recovery_cli('collect','--readonly');runner.recovery_cli('return-baseline')
                with self.assertRaises(ValueError):runner.recovery_board('configure')
                with self.assertRaises(ValueError):runner.recovery_cli('boot-candidate','payload')
                with self.assertRaises(RuntimeError):runner.board('configure')
                self.assertEqual(remote.call_count,2);self.assertEqual(cli.call_count,2)
            with patch.object(window.w,'require_board',side_effect=RuntimeError('expired')), \
                 patch.object(window.w,'ssh') as remote:
                with self.assertRaisesRegex(RuntimeError,'expired'):runner.recovery_board('stop')
                remote.assert_not_called()


class BitstreamTests(unittest.TestCase):
    def sample(self):
        metadata=dict(primaries=[[1,2],[3,4],[5,6]],white=[7,8],luminance=[10000000,50],cll=[1000,400])
        # Independent BE payload, including emulation prevention in luminance.
        data=bytes.fromhex('000000014e018918000100020003000400050006000700080098968000000032900403e8019080')
        rbsp=data[6:];escaped=bytearray();zeros=0
        for byte in rbsp:
            if zeros==2 and byte<=3: escaped.append(3);zeros=0
            escaped.append(byte);zeros=zeros+1 if byte==0 else 0
        data=data[:6]+escaped+bytes.fromhex('000000012601ab')
        return metadata,data

    def test_nonzero_sei_byte_fidelity_with_emulation_prevention(self):
        metadata,data=self.sample()
        result=inspect.check_sei(data,metadata)
        self.assertTrue(result['nonzero_source'])
        self.assertTrue(result['matches_hdmi'])
        metadata['cll'][0]+=1
        with self.assertRaisesRegex(ValueError,'differ'):inspect.check_sei(data,metadata)

    def test_late_duplicate_and_truncated_sei_rejected(self):
        _,data=self.sample()
        with self.assertRaisesRegex(ValueError,'late|duplicate'):inspect.sei(data+data)
        with self.assertRaisesRegex(ValueError,'truncated'):inspect.sei(bytes.fromhex('0000014e01891800'))

    def test_ffmpeg_trace_rejects_conflicting_and_missing_colour_fields(self):
        trace='''[trace_headers @ 0x123] 27 general_profile_idc 00010 = 2
[trace_headers @ 0x123] 171 bit_depth_luma_minus8 011 = 2
[trace_headers @ 0x123] 174 bit_depth_chroma_minus8 011 = 2
[trace_headers @ 0x123] 232 video_full_range_flag 0 = 0
[trace_headers @ 0x123] 234 colour_primaries 00001001 = 9
[trace_headers @ 0x123] 242 transfer_characteristics 00010000 = 16
[trace_headers @ 0x123] 250 matrix_coefficients 00001001 = 9'''
        inspect.check_trace(trace,True)
        with self.assertRaisesRegex(ValueError,'matrix_coefficients'):
            inspect.check_trace(trace.rsplit('\n',1)[0],True)
        with self.assertRaisesRegex(ValueError,'general_profile_idc'):
            inspect.check_trace(trace+'\n[trace_headers @ 0x123] 27 general_profile_idc 00001 = 1',True)


class BoardRecoveryTests(unittest.TestCase):
    def test_metadata_requests_uapi_ids_sizes_and_decodes_nonzero_native_layout(self):
        node=Mock();node.parent.name='video7';node.read_text.return_value='t7-vdin-test\n'
        def ioctl(fd,request,query):
            self.assertEqual((fd,request,query.count),(42,0xc0205647,2))
            self.assertEqual(ctypes.sizeof(query),32)
            self.assertEqual([(v.id,v.size) for v in query.controls[:2]],[(0xa50901,24),(0xa50900,4)])
            self.assertEqual(ctypes.sizeof(query.controls[0]),20)
            # UAPI groups all x coordinates, then all y coordinates.
            ctypes.memmove(query.controls[0].ptr,struct.pack('<8H2I',11,12,13,21,22,23,31,32,100000,5),24)
            ctypes.memmove(query.controls[1].ptr,struct.pack('<2H',1000,400),4)
        with patch.object(Path,'glob',return_value=[node]),patch.object(board.os,'open',return_value=42), \
             patch.object(board.os,'close') as close,patch.object(fcntl,'ioctl',side_effect=ioctl):
            self.assertEqual(json.loads(json.dumps(board.metadata())),dict(primaries=[[11,21],[12,22],[13,23]],
                white=[31,32],luminance=[100000,5],cll=[1000,400]))
        close.assert_called_once_with(42)

    @unittest.skipUnless(sys.platform.startswith('linux'),'requires Linux UAPI headers and C compiler')
    def test_metadata_ids_and_layout_match_installed_linux_uapi(self):
        source='''#include <linux/videodev2.h>
#include <linux/v4l2-controls.h>
#include <stdio.h>
int main(void) { printf("%u %u %zu %zu %zu %zu",V4L2_CID_COLORIMETRY_HDR10_CLL_INFO,
 V4L2_CID_COLORIMETRY_HDR10_MASTERING_DISPLAY,sizeof(struct v4l2_ctrl_hdr10_cll_info),
 sizeof(struct v4l2_ctrl_hdr10_mastering_display),sizeof(struct v4l2_ext_control),sizeof(struct v4l2_ext_controls)); }
'''
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'uapi.c';binary=Path(tmp)/'uapi';c.write_text(source)
            subprocess.run(['cc','-Wall','-Werror',str(c),'-o',str(binary)],check=True)
            values=list(map(int,subprocess.check_output([str(binary)],text=True).split()))
            self.assertEqual(values,[board.V4L2_CID_COLORIMETRY_HDR10_CLL_INFO,
                board.V4L2_CID_COLORIMETRY_HDR10_MASTERING_DISPLAY,4,24,20,32])

    def test_exact_config_recovery_after_api_rewrites_policy_and_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);policy=root/'policy';absent=root/'absent'
            original=b'# exact bytes\nHDR_SDR_ENABLED=1\n';policy.write_bytes(original);policy.chmod(0o640)
            checkpoint=root/'checkpoint.json'
            def api(path,value=None,method=None):
                if value is None:return {'mode':'h265'} if path=='stream/mode' else {'output':{'hdr':False}}
                policy.write_text('API changed policy');absent.write_text('API created file')
            with patch.object(board,'FILES',[str(policy),str(absent)]), \
                 patch.object(board,'PROTECTED',[str(policy)]), \
                 patch.object(board,'api',side_effect=api), \
                 patch.object(board.subprocess,'run'):
                board.save(checkpoint)
                policy.write_bytes(b'candidate');absent.write_text('candidate')
                board.restore(checkpoint)
            self.assertEqual(policy.read_bytes(),original)
            self.assertEqual(policy.stat().st_mode & 0o777,0o640)
            self.assertFalse(absent.exists())
