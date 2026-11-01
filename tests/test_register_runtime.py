import importlib.util
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('register_runtime', 'packaging/kernel-edge/register-runtime.py')
boot = load('profile_boot', 'board/vim4boot.py')


class BootProfileTest(unittest.TestCase):
    def test_install_resumes_only_with_the_complete_identical_module_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'release'
            root.mkdir()
            (root / 'wave5.ko').write_bytes(b'matched module')
            (root / 'modules.dep').write_text('wave5.ko:\n')
            expected = {p.name: runtime.digest(p) for p in root.iterdir()}
            with patch.object(runtime.subprocess, 'run') as extract:
                runtime.install_complete_modules(Path('unused.tar.gz'), root, expected)
                extract.assert_not_called()
            (root / 'wave5.ko').write_bytes(b'mixed module')
            with patch.object(runtime.subprocess, 'run') as extract:
                with self.assertRaisesRegex(ValueError, 'existing module set'):
                    runtime.install_complete_modules(Path('unused.tar.gz'), root, expected)
                extract.assert_not_called()

    def test_install_does_not_resume_with_an_extra_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'release'
            root.mkdir()
            (root / 'wave5.ko').write_bytes(b'matched module')
            expected = {'wave5.ko': runtime.digest(root / 'wave5.ko')}
            (root / 'old.ko').write_bytes(b'unmatched old module')
            with patch.object(runtime.subprocess, 'run') as extract:
                with self.assertRaisesRegex(ValueError, 'existing module set'):
                    runtime.install_complete_modules(Path('unused.tar.gz'), root, expected)
                extract.assert_not_called()

    def test_unified_install_rejects_mixed_modules_before_touching_boot_or_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'extlinux.conf'
            original = b'DEFAULT Default\nLABEL Default\n LINUX /vendor\n'
            config.write_bytes(original)
            (root / 'vendor').write_bytes(b'Linux version 5.15.137-vim4kvm-test (builder)')
            version = '7.3.0-vim4kvm-uhd6+'
            payload = root / 'payload'
            payload.mkdir()
            (payload / 'Image').write_bytes(b'Linux version ' + version.encode() + b' (builder)')
            with tarfile.open(payload / 'modules.tar.gz', 'w:gz') as archive:
                member = tarfile.TarInfo(version + '/kernel/wave5.ko')
                member.size = 5
                archive.addfile(member, io.BytesIO(b'mixed'))
            (payload / 'manifest.json').write_text(json.dumps(dict(
                release=version, modules={'kernel/wave5.ko': hashlib.sha256(b'expected').hexdigest()})))
            (payload / 'candidate.json').write_text(json.dumps(dict(sha256={
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in payload.iterdir()})))
            package = root / 'candidate.tar.gz'
            with tarfile.open(package, 'w:gz') as archive:
                for path in payload.iterdir():
                    archive.add(path, arcname=path.name)
            board = SimpleNamespace(BOOT=root, CONFIG=config,
                                    boot_entries=boot.boot_entries, default_label=boot.default_label)
            original_is_symlink = Path.is_symlink
            with patch.object(runtime.os, 'geteuid', return_value=0), patch.dict(
                    sys.modules, {'vim4boot': board}), patch.object(
                    Path, 'is_symlink', lambda p: str(p) == '/lib' or original_is_symlink(p)), patch.object(
                    runtime.subprocess, 'run') as run, patch.object(runtime.shutil, 'copyfile') as copy:
                with self.assertRaisesRegex(ValueError, 'mismatched module archive'):
                    runtime.install(SimpleNamespace(archive=package))
                run.assert_not_called()
                copy.assert_not_called()
            self.assertEqual(config.read_bytes(), original)

    def test_vendor_release_can_be_read_after_boot_image_compression(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'Image'
            data = b'\0Linux version 5.15.137-vim4kvm-vapb1 (builder)\0'
            for payload in (data, gzip.compress(data)):
                image.write_bytes(payload)
                self.assertEqual(runtime.release(image), '5.15.137-vim4kvm-vapb1')

    def test_final_release_still_requires_matching_installed_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'edge').mkdir()
            (root / 'edge/Image').write_bytes(b'wrong installed Image')
            proof = root / 'proof.json'
            with patch.object(runtime.os, 'geteuid', return_value=0), patch.dict(
                    sys.modules, {'vim4boot': SimpleNamespace(BOOT=root)}):
                for release, error in (
                    ('7.3.0-vim4kvm-uhd1+', 'Image differs'),
                    ('7.3.0-rc7-vim4kvm-uhd1+', 'Image differs'),
                    ('7.3.0-unmatched', 'No validated application'),
                ):
                    with self.subTest(release=release):
                        proof.write_text(json.dumps({'release': release, 'image_sha256': '0' * 64}))
                        with self.assertRaisesRegex(ValueError, error):
                            runtime.register(SimpleNamespace(proof=proof))

    def test_profile_upgrade_preserves_default_and_all_other_entries(self):
        source = {'APPEND': 'root=UUID=test console=ttyAML0 vim4.one_kvm=1 systemd.mask=vim4-manager.service'}
        previous = runtime.boot_profile(source)
        full = runtime.boot_profile(source, ['binder.service', 'bluetooth-khadas.service'])
        block = lambda label, fields: '\nLABEL ' + label + '\n' + ''.join(
            f'  {key} {value}\n' for key, value in fields.items())
        # Even an identical append line under another label must not be changed.
        text = 'DEFAULT Default\n' + block('Default', {'LINUX': '/Image', 'APPEND': 'vendor keep'})
        text += block('Other', previous) + block('FullKvm', previous)
        result = runtime.update_boot_entry(text, previous, previous, full)
        before, after = boot.boot_entries(text), boot.boot_entries(result)
        self.assertEqual(boot.default_label(result), 'Default')
        self.assertEqual(after['Default'], before['Default'])
        self.assertEqual(after['Other'], before['Other'])
        self.assertEqual(after['FullKvm'], full)
        self.assertIn('root=UUID=test console=ttyAML0', full['APPEND'])
        self.assertNotIn('systemd.mask=vim4-manager.service', full['APPEND'])
        self.assertEqual(runtime.update_boot_entry(result, full, previous, full), result)

    def test_custom_full_profile_is_never_replaced(self):
        previous = runtime.boot_profile({'APPEND': 'root=test'})
        custom = {**previous, 'APPEND': previous['APPEND'] + ' administrator=keep'}
        with self.assertRaisesRegex(ValueError, 'custom boot arguments'):
            runtime.update_boot_entry('DEFAULT FullKvm\n', custom, previous,
                                      runtime.boot_profile({'APPEND': 'root=test'}, ['binder.service']))

    def test_framebuffer_console_upgrade_keeps_serial_preferred_and_other_entries(self):
        source = {'APPEND': 'root=test console=ttyS0,921600n8'}
        previous = runtime.boot_profile(source, ['binder.service'])
        full = runtime.boot_profile(source, ['binder.service'], framebuffer_console=True)
        text = 'DEFAULT FullKvm\nLABEL Other\n APPEND administrator=keep\nLABEL FullKvm\n'
        text += ''.join(f' {key} {value}\n' for key, value in previous.items())
        result = runtime.update_boot_entry(text, previous, previous, full)
        fields = boot.boot_entries(result)
        self.assertEqual(fields['Other']['APPEND'], 'administrator=keep')
        consoles = [word for word in fields['FullKvm']['APPEND'].split() if word.startswith('console=')]
        self.assertEqual(consoles, ['console=tty0', 'console=ttyS0,921600n8'])
        self.assertEqual(runtime.update_boot_entry(result, full, previous, full), result)
