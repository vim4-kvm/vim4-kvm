"""A user-space-only revision needs its own RAM directory and matching PID1."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from test_display_once import once, static_elf

ROOT = Path(__file__).resolve().parents[1]


class HDR10PayloadTest(unittest.TestCase):
    def fixture(self, root, init_parent):
        bundle, template = root / 'bundle', root / 'template'
        bundle.mkdir()
        template.mkdir()
        release = '7.3.0-vim4kvm-hdr10r3+'
        modules = {'kernel/xt_DSCP.ko': b'upper', 'kernel/xt_dscp.ko': b'lower'}
        with tarfile.open(bundle / 'modules.tar.gz', 'w:gz') as archive:
            for name, value in modules.items():
                member = tarfile.TarInfo(release + '/' + name)
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
        (bundle / 'gstreamer-1.0').mkdir()
        for name in ('Image', 'vim4.dtb', 'one-kvm', 'hdr10-prepare', 'hdr10-run',
                     'gstreamer-1.0/libgstvfmcap.so', 'gstreamer-1.0/libgstvideo4linux2.so'):
            (bundle / name).write_bytes(name.encode())
        (bundle / 'manifest.json').write_text(json.dumps(dict(
            release=release, source='a' * 40, kernel_build_id='1' * 40,
            modules={key: hashlib.sha256(value).hexdigest() for key, value in modules.items()})))
        (bundle / 'candidate.json').write_text(json.dumps(dict(sha256={
            str(path.relative_to(bundle)): once.sha(path)
            for path in bundle.rglob('*') if path.is_file()})))
        prefix = '/var/lib/vim4-kvm/hdr2-unified/' + '1' * 40
        (template / 'extlinux.conf').write_text(
            f'LINUX {prefix}/Image\nFDT {prefix}/vim4.dtb\nAPPEND init={prefix}/init\n')
        init = root / 'init'
        init.write_bytes(static_elf() + init_parent.encode() + b'\0')
        return [sys.executable, str(ROOT / 'packaging/hdr10/ram-payload.py'),
                str(bundle), str(template), str(root / 'payload'), str(init),
                '--payload-id', 'r6-p010caps']

    def test_namespaced_revision_preserves_modules_and_real_build_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = self.fixture(root, '/var/lib/vim4-kvm/ram-candidates/hdr10/r6-p010caps/')
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with tarfile.open(root / 'payload.tar.gz') as archive:
                plan, metadata, entries = once.read_trial(archive)
                self.assertEqual(plan['build_id'], '1' * 40)
                self.assertEqual(plan['payload_id'], 'r6-p010caps')
                self.assertIn('ram-candidates/hdr10/r6-p010caps/', plan['command'])
                for name, expected in plan['files'].items():
                    self.assertEqual(hashlib.sha256(archive.extractfile(entries[name]).read()).hexdigest(), expected)
                modules = [name for name in entries if name.startswith('modules/')]
                self.assertEqual(len(modules), 2)
                launcher = archive.extractfile('runtime/vim4-kvm-run').read().decode()
                self.assertIn(str(once.candidate_prefix(plan)), launcher)

    def test_old_pid1_is_rejected_before_creating_new_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = self.fixture(root, '/var/lib/vim4-kvm/hdr2-unified/')
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('TRIAL_ROOT does not match', result.stderr)
            self.assertFalse((root / 'payload').exists())
