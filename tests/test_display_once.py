"""A trial can be interrupted without replacing any persistent baseline file."""
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('display_once', ROOT / 'packaging/kernel-edge/display-once.py')
once = importlib.util.module_from_spec(spec)
spec.loader.exec_module(once)
FORMAL_RELEASE = once.formal_baseline()["release"]


def static_elf(kind=1):
    data = bytearray(120)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 2, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, 1)
    struct.pack_into('<I', data, 64, kind)
    return data


class TrialTest(unittest.TestCase):
    def test_same_formal_image_distinct_dt_stages_and_keeps_installed_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.fixture(root, release=FORMAL_RELEASE, baseline_release=FORMAL_RELEASE)
            payload = root / 'payload'
            report = json.loads((payload/'manifest.json').read_text())
            state = json.loads((root/'baseline.json').read_text())
            state.update(release=FORMAL_RELEASE, build_id=report['kernel_build_id'])
            state['dt_properties'] = {'soc/display/status': '64697361626c656400'}
            state['files']['/boot/kernels/'+FORMAL_RELEASE+'/Image'] = once.sha(payload/'Image')
            state['files']['/boot/kernels/'+FORMAL_RELEASE+'/vim4.dtb'] = '0'*64
            state['files'].update({'/lib/modules/'+FORMAL_RELEASE+'/'+name: digest
                                   for name, digest in report['modules'].items()})
            (root/'baseline.json').write_text(json.dumps(state))
            report['dt_properties'] = {'soc/display/status': '6f6b617900'}
            (payload/'manifest.json').write_text(json.dumps(report))
            modules = root/'installed-modules'/FORMAL_RELEASE
            modules.mkdir(parents=True)
            (modules/'overlay.ko').write_bytes(b'keep this installed overlay')
            with patch.object(once, 'ROOT', root/'display-m1'), patch.object(
                    once, 'MODULE_ROOT', modules.parent), patch.object(once.os, 'geteuid', return_value=0):
                parent = once.candidate_parent(dict(namespace='passthrough', payload_id='dt-v1'))
                (root/'init').write_bytes(static_elf() + (str(parent)+'/').encode() + b'\0')
                with patch.object(once.subprocess, 'check_output', return_value='6f 6b 61 79 00'):
                    once.prepare(payload, root/'init', root/'baseline.json', root/'same-image',
                                 release=FORMAL_RELEASE, baseline_release=FORMAL_RELEASE,
                                 baseline_id=state['build_id'], namespace='passthrough', payload_id='dt-v1')
                sha = once.sha
                def protected_hash(path):
                    return state['files'][str(path)] if str(path) in state['files'] else sha(path)
                with patch.object(once, 'sha', side_effect=protected_hash):
                    once.stage(root/'same-image/candidate.tar', retained_baseline=state)
                plan = json.loads((root/'same-image/trial.json').read_text())
                self.assertEqual(plan['dt_properties'], report['dt_properties'])
                self.assertEqual(plan['build_id'], plan['baseline_id'])
                with patch.object(once.os, 'uname', return_value=SimpleNamespace(release=FORMAL_RELEASE)):
                    once.cleanup_module_mountpoint(plan)
                self.assertEqual((modules/'overlay.ko').read_bytes(), b'keep this installed overlay')
                with patch.object(once.subprocess, 'check_output', return_value='00'):
                    with self.assertRaisesRegex(ValueError, 'DT property mismatch'):
                        once.prepare(payload, root/'init', root/'baseline.json', root/'bad-dt',
                                     release=FORMAL_RELEASE, baseline_release=FORMAL_RELEASE,
                                     baseline_id=state['build_id'], namespace='passthrough', payload_id='dt-v1')
                # A different DTB hash with an unchanged readable identity must
                # fail both prepare and stage, including direct metadata input.
                unchanged = dict(state, dt_properties=report['dt_properties'])
                (root/'baseline.json').write_text(json.dumps(unchanged))
                with self.assertRaisesRegex(ValueError, 'DT identity must differ'):
                    once.prepare(payload, root/'init', root/'baseline.json', root/'unchanged',
                                 release=FORMAL_RELEASE, baseline_release=FORMAL_RELEASE,
                                 baseline_id=state['build_id'], namespace='passthrough', payload_id='dt-v1')
                with self.assertRaisesRegex(ValueError, 'DT identity must differ'):
                    once.stage(root/'same-image/candidate.tar', retained_baseline=unchanged)
                # The direct HDR2 manifest path must enforce the same rule;
                # a caller cannot bypass prepare by supplying another metadata format.
                manifest = dict(release=plan['release'], build_id=plan['build_id'], source_commit=plan['source'],
                                sha256=plan['files'], namespace=plan['namespace'], payload_id=plan['payload_id'],
                                dt_properties=state['dt_properties'])
                with tarfile.open(root/'same-image/candidate.tar') as original, tarfile.open(root/'ambiguous.tar', 'w') as ambiguous:
                    for member in original:
                        if member.name != 'trial.json':
                            ambiguous.addfile(member, original.extractfile(member))
                    data = json.dumps(manifest).encode()
                    member = tarfile.TarInfo('manifest.json')
                    member.size = len(data)
                    ambiguous.addfile(member, io.BytesIO(data))
                with self.assertRaisesRegex(ValueError, 'DT identity must differ'):
                    once.stage(root/'ambiguous.tar', retained_baseline=state)
            for p in root.rglob('*'):
                if p.is_dir():
                    p.chmod(0o755)

    def test_release_tags_are_generic_but_remain_single_safe_path_components(self):
        for tag in ('hdr10r3', 'future_codec.42', 'uhd4-debug'):
            with tempfile.TemporaryDirectory() as directory:
                self.fixture(Path(directory), release='7.3.0-vim4kvm-' + tag + '+')
        for release in ('7.3.0-vim4kvm-../bad+', '7.3.0-vim4kvm-+',
                        '7.3.0-vim4kvm-tag+/extra', '7.4.0-vim4kvm-tag+'):
            with self.assertRaises(ValueError):
                once.validate_release(release)

    def test_filesystem_uuid_needs_verified_partition_for_no_initramfs_boot(self):
        state = dict(cmdline='root=UUID=filesystem rw rootflags=data=ordered')
        with self.assertRaisesRegex(ValueError, 'root_partuuid proof'):
            once.trial_cmdline(state)
        state['root_partuuid'] = '../wrong'
        with self.assertRaises(ValueError):
            once.trial_cmdline(state)
        state['root_partuuid'] = 'bcb80000-02'
        self.assertEqual(once.trial_cmdline(state),
                         'root=PARTUUID=bcb80000-02 rw rootflags=data=ordered rootwait')
        self.assertIn('root=UUID=filesystem', state['cmdline'])

    def fixture(self, root, case_pair=False, release=once.RELEASE,
                baseline_release='5.15.137-vim4kvm-hdrdual6'):
        payload = root / 'payload'
        payload.mkdir()
        (root / 'init').write_bytes(static_elf())
        lower = 'xt_dscp.ko' if case_pair else 'xt_dscp_lower.ko'
        modules = {'kernel/net/xt_DSCP.ko': b'upper', 'kernel/net/' + lower: b'lower'}
        with tarfile.open(payload / 'modules.tar.gz', 'w:gz') as archive:
            for name, data in modules.items():
                member = tarfile.TarInfo(release + '/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        (payload / 'Image').write_bytes(b'candidate image')
        (payload / 'vim4.dtb').write_bytes(b'candidate dtb')
        (payload / 'manifest.json').write_text(json.dumps(dict(
            source='a' * 40, kernel_build_id='1' * 40, release=release,
            modules={name: once.hashlib.sha256(data).hexdigest() for name, data in modules.items()},
            artifacts={name: once.sha(payload / name) for name in ('Image', 'vim4.dtb', 'modules.tar.gz')})))
        boot = '/boot/edge' if baseline_release.startswith('5.15.') else '/boot/kernels/'+baseline_release
        state = dict(release=baseline_release, build_id='a'*40, cmdline='root=PARTUUID=bcb80000-02 rootwait rw', files={name: 'f' * 64 for name in (
            boot+'/Image', boot+'/vim4.dtb', '/boot/extlinux/extlinux.conf',
            '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json')})
        if '-npu' in release or release in ('7.3.0-vim4kvm-uhd2+', '7.3.0-vim4kvm-uhd2-nodebug+', '7.3.0-vim4kvm-uhd3+', '7.3.0-vim4kvm-uhd4+'):
            runtime = {}
            for index, target in enumerate(('/usr/libexec/vim4-board-runtime',
                    '/usr/libexec/vim4-kvm-run', '/usr/libexec/vim4-mainline-prepare',
                    '/usr/libexec/vim4-mainline-gadget-prepare',
                    '/opt/vim4-onekvm-edge/one-kvm-edge')):
                relative = f'helper-{index}'
                (payload / relative).write_bytes(b'candidate helper')
                digest = once.sha(payload / relative)
                runtime[relative] = dict(target=target, sha256=digest)
                state['files'][target] = digest
            (payload / 'runtime-files.json').write_text(json.dumps(dict(files=runtime)))
        (root / 'baseline.json').write_text(json.dumps(state))
        once.prepare(payload, root / 'init', root / 'baseline.json', root / 'bundle',
                     release=release, baseline_release=baseline_release)
        return root / 'bundle/candidate.tar'

    def test_independent_npu_release_preserves_baseline_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.fixture(root, release='7.3.0-vim4kvm-npu1+',
                                   baseline_release='5.15.137-vim4kvm-hdrdual6')
            plan = json.loads((root / 'bundle/trial.json').read_text())
            self.assertEqual(plan['baseline_release'], '5.15.137-vim4kvm-hdrdual6')
            self.assertEqual(plan['release'], '7.3.0-vim4kvm-npu1+')
            with tarfile.open(archive) as trial:
                config = trial.extractfile('extlinux.conf').read().decode()
            self.assertIn('t7_hdmirx.phy_test=1', config)
            self.assertIn('t7_hdmirx.hdr_capture=1', config)
            self.assertIn('t7_vdin_test.direct_dma=1', config)
            self.assertIn('cma=512M@0x10000000-0xf0000000', config)
            self.assertIn('modprobe.blacklist=crg_udc,t7_hdmirx,t7_vdin_test,wave5', config)
            self.assertNotIn('t7_hdmirx.', plan['baseline_cmdline'])
            with tarfile.open(archive) as trial:
                modules = [name for name in trial.getnames() if name.startswith('modules/')]
                self.assertTrue(modules)
                self.assertTrue(all('/7.3.0-vim4kvm-npu1+/' in name for name in modules))
            state = json.loads((root / 'baseline.json').read_text())
            state['files']['/usr/libexec/vim4-kvm-run'] = '0' * 64
            (root / 'baseline.json').write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, 'helper differs'):
                once.prepare(root / 'payload', root / 'init', root / 'baseline.json',
                             root / 'rejected', release='7.3.0-vim4kvm-npu1+')

    def test_uhd2_keeps_npu_memory_and_runtime_proof_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.fixture(root, release='7.3.0-vim4kvm-uhd2+',
                                   baseline_release='5.15.137-vim4kvm-hdrdual6')
            with tarfile.open(archive) as trial:
                config = trial.extractfile('extlinux.conf').read().decode()
                modules = [p for p in trial.getnames() if p.startswith('modules/')]
            self.assertIn('cma=512M@0x10000000-0xf0000000', config)
            self.assertIn('t7_hdmirx.hdr_capture=1', config)
            self.assertTrue(all('/7.3.0-vim4kvm-uhd2+/' in p for p in modules))
            state = json.loads((root / 'baseline.json').read_text())
            state['files']['/usr/libexec/vim4-kvm-run'] = '0' * 64
            (root / 'baseline.json').write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, 'helper differs'):
                once.prepare(root / 'payload', root / 'init', root / 'baseline.json',
                             root / 'rejected', release='7.3.0-vim4kvm-uhd2+')

    def test_nodebug_release_keeps_matching_modules_and_video_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.fixture(root, release='7.3.0-vim4kvm-uhd2-nodebug+',
                                   baseline_release='5.15.137-vim4kvm-hdrdual6')
            with tarfile.open(archive) as trial:
                config = trial.extractfile('extlinux.conf').read().decode()
                modules = [p for p in trial.getnames() if p.startswith('modules/')]
            self.assertIn('cma=512M@0x10000000-0xf0000000', config)
            self.assertIn('t7_hdmirx.hdr_capture=1', config)
            self.assertTrue(all('/7.3.0-vim4kvm-uhd2-nodebug+/' in p for p in modules))

    def test_uhd4_matches_private_modules_and_video_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.fixture(root, release='7.3.0-vim4kvm-uhd4+',
                                   baseline_release='5.15.137-vim4kvm-hdrdual6')
            with tarfile.open(archive) as trial:
                config = trial.extractfile('extlinux.conf').read().decode()
                modules = [p for p in trial.getnames() if p.startswith('modules/')]
            self.assertIn('cma=512M@0x10000000-0xf0000000', config)
            self.assertIn('t7_hdmirx.hdr_capture=1', config)
            self.assertTrue(all('/7.3.0-vim4kvm-uhd4+/' in p for p in modules))

    def test_boot_files_remain_default_through_stage_reset_and_interruption(self):
        for fail_after in (None, 1, 4):
            with self.subTest(fail_after=fail_after), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                bundle = self.fixture(root)
                boot = root / 'boot'
                boot.mkdir()
                for name in ('Image', 'vim4.dtb', 'extlinux.conf'):
                    (boot / name).write_bytes(b'retained baseline ' + name.encode())
                before = {p.name: p.read_bytes() for p in boot.iterdir()}
                calls = 0

                def interrupted_copy(source, output):
                    nonlocal calls
                    calls += 1
                    output.write(source.read())
                    if calls == fail_after:
                        raise OSError('simulated interrupted extraction')

                trial_root = root / 'trials'
                with patch.object(once, 'ROOT', trial_root), patch.object(once, 'preflight'), \
                        patch.object(once.shutil, 'copyfileobj', interrupted_copy):
                    if fail_after:
                        with self.assertRaisesRegex(OSError, 'interrupted'):
                            once.stage(bundle)
                        self.assertFalse((trial_root / ('1' * 40)).exists())
                    else:
                        once.stage(bundle)
                        candidate = trial_root / ('1' * 40)
                        self.assertEqual((candidate / 'modules' / once.RELEASE / 'kernel/net/xt_DSCP.ko').read_bytes(), b'upper')
                        self.assertEqual((candidate / 'modules' / once.RELEASE / 'kernel/net/xt_dscp_lower.ko').read_bytes(), b'lower')
                        config = (candidate / 'extlinux.conf').read_text()
                        self.assertIn('oops=panic panic=20 init=', config)
                        self.assertNotIn('saveenv', (candidate / 'trial.json').read_text())
                        # A reset starts the unchanged default configuration. No
                        # userspace completion/cleanup callback is required.
                        for path in candidate.rglob('*'):
                            if path.is_dir():
                                path.chmod(0o755)
                        candidate.chmod(0o755)
                self.assertEqual(before, {p.name: p.read_bytes() for p in boot.iterdir()})

    def test_prepare_keeps_case_distinct_modules_in_archive_on_macos(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self.fixture(Path(directory), case_pair=True)
            with tarfile.open(bundle) as archive:
                prefix = 'modules/' + once.RELEASE + '/kernel/net/'
                self.assertEqual(archive.extractfile(prefix + 'xt_DSCP.ko').read(), b'upper')
                self.assertEqual(archive.extractfile(prefix + 'xt_dscp.ko').read(), b'lower')

    def test_window_process_death_leaves_only_an_inert_partial_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            bundle = self.fixture(root)
            baseline = root / 'default-extlinux.conf'
            baseline.write_bytes(b'DEFAULT baseline\nLABEL baseline\nLINUX /edge/Image\n')
            child = r'''
import importlib.util, os, sys
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('once', sys.argv[1])
once = importlib.util.module_from_spec(spec)
spec.loader.exec_module(once)
once.ROOT = Path(sys.argv[2])
once.preflight = lambda plan: None
def die(source, output):
    output.write(source.read(1))
    output.flush()
    os._exit(91)  # No finally blocks, atexit hooks or rollback opportunity.
with patch.object(once.shutil, 'copyfileobj', die):
    once.stage(Path(sys.argv[3]))
'''
            result = subprocess.run([os.sys.executable, '-c', child, str(spec.origin),
                                     str(root / 'trials'), str(bundle)])
            self.assertEqual(result.returncode, 91)
            self.assertEqual(baseline.read_bytes(), b'DEFAULT baseline\nLABEL baseline\nLINUX /edge/Image\n')
            self.assertFalse((root / 'trials' / ('1' * 40)).exists())
            partial = list((root / 'trials').glob('.incomplete-*'))
            self.assertEqual(len(partial), 1)
            self.assertTrue(any(p.is_file() for p in partial[0].rglob('*')))

    def test_wrong_baseline_refuses_staging_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.fixture(root)
            with patch.object(once, 'ROOT', root / 'trials'), patch.object(once.os, 'geteuid', return_value=0), \
                    patch.object(once.os, 'uname') as uname, patch.object(once, 'running_build_id', return_value='2' * 40):
                uname.return_value.release = '5.15.test'
                with self.assertRaisesRegex(RuntimeError, 'approved running baseline'):
                    once.stage(bundle)
                self.assertFalse((root / 'trials').exists())

    def test_changed_root_partition_refuses_staging(self):
        plan = dict(baseline_release='5.15.test', baseline_id='a'*40,
                    release=once.RELEASE, baseline_cmdline='root=UUID=filesystem rw',
                    root_partuuid='bcb80000-02', baseline_files={})
        with patch.object(once.os, 'geteuid', return_value=0), \
                patch.object(once.os, 'uname') as uname, \
                patch.object(once, 'running_build_id', return_value='a'*40), \
                patch.object(Path, 'read_text', return_value=plan['baseline_cmdline']), \
                patch.object(Path, 'stat', return_value=SimpleNamespace(st_rdev=1, st_dev=2)):
            uname.return_value.release = '5.15.test'
            with self.assertRaisesRegex(RuntimeError, 'root partition differs'):
                once.preflight(plan)

    def test_dynamic_or_truncated_init_and_unsafe_archive_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'init'
            for data in (static_elf(2), static_elf(3), static_elf()[:80]):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    once.static_arm64(path)
        for name, kind in (('../Image', tarfile.REGTYPE), ('/boot/Image', tarfile.REGTYPE),
                           ('modules/link', tarfile.SYMTYPE), ('device', tarfile.CHRTYPE)):
            member = tarfile.TarInfo(name)
            member.type = kind
            with self.assertRaises(ValueError):
                once.safe_member(member)

    @unittest.skipUnless(platform.system() == 'Linux', 'PID 1 mount ABI harness requires Linux headers')
    def test_real_pid1_never_executes_systemd_before_verified_readonly_modules(self):
        harness = ROOT / 'tests/fixtures/display-once-init-harness.c'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'init-test'
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(output)], check=True)
            subprocess.run([str(output)], check=True)


if __name__ == '__main__':
    unittest.main()
