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


def static_elf(kind=1):
    data = bytearray(120)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 2, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, 1)
    struct.pack_into('<I', data, 64, kind)
    return data


class TrialTest(unittest.TestCase):
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
                baseline_release=once.RELEASE):
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
        state = dict(cmdline='root=PARTUUID=bcb80000-02 rootwait rw', files={name: 'f' * 64 for name in (
            '/boot/edge/Image', '/boot/edge/vim4.dtb', '/boot/extlinux/extlinux.conf',
            '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json')})
        if '-npu' in release:
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

                # The staging test uses a temporary directory owned by the test user;
                # production checks root ownership and the live build ID separately.
                real_lstat = Path.lstat

                def owned(path):
                    result = list(real_lstat(path))
                    result[4] = 0
                    result[0] &= ~0o022
                    return os.stat_result(result)

                trial_root = root / 'trials'
                with patch.object(once, 'ROOT', trial_root), patch.object(once, 'preflight'), \
                        patch.object(Path, 'lstat', owned), \
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
real_lstat = Path.lstat
def owned(path):
    fields = list(real_lstat(path))
    fields[4] = 0
    fields[0] &= ~0o022
    return os.stat_result(fields)
def die(source, output):
    output.write(source.read(1))
    output.flush()
    os._exit(91)  # No finally blocks, atexit hooks or rollback opportunity.
with patch.object(Path, 'lstat', owned), patch.object(once.shutil, 'copyfileobj', die):
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
                uname.return_value.release = once.RELEASE
                with self.assertRaisesRegex(RuntimeError, 'approved running baseline'):
                    once.stage(bundle)
                self.assertFalse((root / 'trials').exists())

    def test_changed_root_partition_refuses_staging(self):
        plan = dict(baseline_release=once.RELEASE, baseline_id=once.BASE_ID,
                    release=once.RELEASE, baseline_cmdline='root=UUID=filesystem rw',
                    root_partuuid='bcb80000-02', baseline_files={})
        with patch.object(once.os, 'geteuid', return_value=0), \
                patch.object(once.os, 'uname') as uname, \
                patch.object(once, 'running_build_id', return_value=once.BASE_ID), \
                patch.object(Path, 'read_text', return_value=plan['baseline_cmdline']), \
                patch.object(Path, 'stat', return_value=SimpleNamespace(st_rdev=1, st_dev=2)):
            uname.return_value.release = once.RELEASE
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
