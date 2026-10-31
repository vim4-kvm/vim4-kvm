import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import test_display_once as fixtures

once, ROOT = fixtures.once, fixtures.ROOT


class PayloadTest(unittest.TestCase):
    def bundle(self, directory, identity, content):
        directory.mkdir()
        old = fixtures.TrialTest().fixture(directory)
        with tarfile.open(old) as archive:
            data = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
        plan = json.loads(data.pop('trial.json'))
        plan.update(namespace='kbase', payload_id=identity)
        prefix = str(once.candidate_prefix(plan, 'trial.json'))
        data['vim4.dtb'] = content
        data['init'] += (str(Path(prefix).parent) + '/').encode() + b'\0'
        data['extlinux.conf'] = (f'LINUX {prefix}/Image\nFDT {prefix}/vim4.dtb\nAPPEND init={prefix}/init\n').encode()
        plan['command'] = f'sysboot mmc 1:2 any ${{pxefile_addr_r}} {prefix}/extlinux.conf; reset'
        plan['files'] = {n: once.hashlib.sha256(v).hexdigest() for n, v in data.items()}
        data['trial.json'] = json.dumps(plan).encode()
        result = directory / 'new.tar'
        with tarfile.open(result, 'w') as archive:
            for name, value in data.items():
                member = tarfile.TarInfo(name); member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
        return result, plan

    def test_two_payloads_share_kernel_and_refuse_existing_or_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'module-mounts').mkdir()
            real = Path.lstat
            def owned(path):
                value = list(real(path)); value[4] = 0; value[0] &= ~0o022
                return os.stat_result(value)
            with patch.object(once, 'ROOT', root / 'legacy'), patch.object(once, 'MODULE_ROOT', root / 'module-mounts'), patch.object(once, 'preflight'), patch.object(Path, 'lstat', owned):
                first, a = self.bundle(root / 'a', 'first', b'dt-a')
                second, b = self.bundle(root / 'b', 'second', b'dt-b')
                once.stage(first); once.stage(second)
                pa = once.candidate_prefix(a, 'trial.json'); pb = once.candidate_prefix(b, 'trial.json')
                self.assertEqual((pa / 'Image').read_bytes(), (pb / 'Image').read_bytes())
                self.assertEqual((pa / 'vim4.dtb').read_bytes(), b'dt-a')
                self.assertEqual((pb / 'vim4.dtb').read_bytes(), b'dt-b')
                with self.assertRaises(FileExistsError): once.stage(first)
                # Even an unrelated or dangling destination is never overwritten.
                third, c = self.bundle(root / 'c', 'third', b'dt-c')
                target = once.candidate_prefix(c, 'trial.json'); target.parent.mkdir(parents=True)
                target.symlink_to(root / 'missing')
                with self.assertRaises(FileExistsError): once.stage(third)
                self.assertTrue(target.is_symlink())
                target.unlink(); target.mkdir(); (target / 'foreign').write_text('keep')
                with self.assertRaises(FileExistsError): once.stage(third)
                self.assertEqual((target / 'foreign').read_text(), 'keep')
                pa.chmod(0o755)  # Test user has no root DAC override for marker unlink.
                with patch.object(once.os, 'geteuid', return_value=0), patch.object(once.os, 'uname') as uname:
                    uname.return_value.release = '5.15.test'
                    once.cleanup_module_mountpoint(b)  # Did not create the shared mountpoint.
                    mount = root / 'module-mounts' / a['release']
                    (mount / 'foreign').touch()
                    with self.assertRaises(OSError): once.cleanup_module_mountpoint(a)
                    (mount / 'foreign').unlink()
                    once.cleanup_module_mountpoint(a)
                    self.assertFalse(mount.exists())
                for path in root.rglob('*'):
                    if path.is_dir(): path.chmod(0o755)

    def test_layout_rejects_unsafe_or_partial_namespace(self):
        for fields in ({'namespace': 'kbase'}, {'namespace': '../bad', 'payload_id': 'x'},
                       {'namespace': 'kbase', 'payload_id': '../x'}):
            with self.assertRaises(ValueError): once.candidate_prefix(dict(fields, build_id='1'*40))
        self.assertEqual(once.candidate_prefix({'build_id': '1'*40}), once.ROOT.parent/'hdr2-unified'/('1'*40))

    @unittest.skipUnless(platform.system() == 'Linux', 'PID1 harness needs Linux mount headers')
    def test_namespaced_pid1_still_rejects_wrong_real_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'pid1'
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-DTRIAL_ROOT="/var/lib/vim4-kvm/ram-candidates/kbase/first/"',
                            str(ROOT/'tests/fixtures/display-once-init-harness.c'), '-o', str(output)], check=True)
            subprocess.run([str(output)], check=True)
