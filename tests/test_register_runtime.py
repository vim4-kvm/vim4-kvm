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


runtime = load('register_runtime', 'packaging/kernel/register-runtime.py')
boot = load('profile_boot', 'board/vim4boot.py')
CURRENT = '7.3.1-vim4-20261103'


class BootProfileTest(unittest.TestCase):
    def test_mainline_profile_keeps_radio_blacklists_and_pd_exclusion_once(self):
        source = {'APPEND': 'root=test module_blacklist=brcmfmac module_blacklist=hci_uart,brcmfmac'}
        full = runtime.boot_profile(source, version=CURRENT)
        blocked = [word for word in full['APPEND'].split() if word.startswith('module_blacklist=')]
        self.assertEqual(blocked, ['module_blacklist=brcmfmac,hci_uart,fusb302'])
        self.assertEqual(runtime.boot_profile(full, version=CURRENT), full)
        old = {**full, 'APPEND': full['APPEND'].replace(',fusb302', '')}
        text = 'DEFAULT Mainline\nLABEL Mainline\n  APPEND ' + old['APPEND'] + '\n'
        updated = runtime.update_boot_entry(text, old, full, full)
        self.assertEqual(boot.boot_entries(updated)['Mainline']['APPEND'], full['APPEND'])

    def test_upgrade_applies_pd_policy_to_mainline_and_matching_registry_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot_root, payload = root/'boot', root/'payload'
            old = '7.3.1-vim4-20261102'
            old_root = boot_root/'kernels'/old
            old_root.mkdir(parents=True)
            payload.mkdir()
            (old_root/'Image').write_bytes(('Linux version ' + old + ' ').encode())
            for name in ('Image', 'vim4.dtb'):
                (payload/name).write_bytes(name.encode())
            fields = {'LINUX': '/kernels/'+old+'/Image', 'FDT': '/kernels/'+old+'/vim4.dtb',
                      'APPEND': 'root=keep module_blacklist=brcmfmac'}
            vendor = {'label': 'Vendor', 'boot': {'LINUX': '/vendor', 'APPEND': 'vendor=keep'}}
            records = [vendor, {'label': 'Mainline', 'release': old, 'boot': fields}]
            manifest = root/'kernels.json'
            manifest.write_text(json.dumps(records))
            text = 'DEFAULT Mainline\nLABEL Vendor\n LINUX /vendor\n APPEND vendor=keep\nLABEL Mainline\n'
            text += ''.join(' '+key+' '+value+'\n' for key,value in fields.items())
            proxy = SimpleNamespace(BOOT=boot_root, MANIFEST=manifest, boot_entries=boot.boot_entries)
            updated, registered = runtime.upgrade_registration(proxy, text.encode(),
                {'release': CURRENT, 'modules': {'kernel/test.ko': 'a'*64}}, payload,
                boot_root/'kernels'/CURRENT)
            self.assertEqual(registered[0], vendor)
            self.assertEqual(boot.boot_entries(updated)['Vendor'], boot.boot_entries(text)['Vendor'])
            current = boot.boot_entries(updated)['Mainline']
            self.assertEqual(current['APPEND'], 'root=keep module_blacklist=brcmfmac,fusb302')
            self.assertEqual(registered[1]['boot'], current)
            self.assertEqual(json.loads(manifest.read_text()), records)

    def test_insufficient_boot_space_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot_root, payload = root / 'boot', root / 'payload'
            boot_root.mkdir()
            payload.mkdir()
            for name in runtime.BOOT_FILES:
                (payload / name).write_bytes(b'candidate')
                (boot_root / name).write_bytes(b'baseline')
            with patch.object(runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
                with self.assertRaisesRegex(ValueError, 'Insufficient /boot'):
                    runtime.check_space(boot_root, payload)
            self.assertEqual((boot_root / 'Image').read_bytes(), b'baseline')
            with patch.object(runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=len(runtime.BOOT_FILES)*4096+100)):
                with self.assertRaisesRegex(ValueError, 'Insufficient /boot'):
                    runtime.check_space(boot_root, payload)
            with patch.object(runtime.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024*1024)):
                runtime.check_space(boot_root, payload)

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
            original = ('DEFAULT Vendor\nLABEL Vendor\n LINUX /vendor\nLABEL Mainline\n LINUX /kernels/'+CURRENT+'/Image\n FDT /kernels/'+CURRENT+'/vim4.dtb\n').encode()
            config.write_bytes(original)
            (root / 'vendor').write_bytes(b'Linux version 5.15.137-vim4kvm-test (builder)')
            retained = root/'kernels'/CURRENT
            retained.mkdir(parents=True)
            (retained/'Image').write_text('Linux version '+CURRENT+' (builder)')
            version = '7.3.1-vim4-20261104'
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
            proof = root / 'proof.json'
            with patch.object(runtime.os, 'geteuid', return_value=0), patch.dict(
                    sys.modules, {'vim4boot': SimpleNamespace(BOOT=root)}):
                for release, error in (
                    (CURRENT, 'Image differs'),
                    ('7.3.1-vim4-20261104', 'Image differs'),
                    ('7.3.0-unmatched', 'No validated application'),
                ):
                    with self.subTest(release=release):
                        installed = root/'kernels'/release
                        installed.mkdir(parents=True)
                        (installed/'Image').write_bytes(b'wrong installed Image')
                        proof.write_text(json.dumps({'release': release, 'image_sha256': '0' * 64}))
                        with self.assertRaisesRegex(ValueError, error):
                            runtime.register(SimpleNamespace(proof=proof))

    def test_profile_upgrade_preserves_default_and_all_other_entries(self):
        source = {'APPEND': 'root=UUID=test console=ttyAML0 vim4.one_kvm=1 systemd.mask=vim4-manager.service'}
        previous = runtime.boot_profile(source, version=CURRENT)
        full = runtime.boot_profile(source, ['binder.service', 'bluetooth-khadas.service'], version=CURRENT)
        block = lambda label, fields: '\nLABEL ' + label + '\n' + ''.join(
            f'  {key} {value}\n' for key, value in fields.items())
        # Even an identical append line under another label must not be changed.
        text = 'DEFAULT Vendor\n' + block('Vendor', {'LINUX': '/Image', 'APPEND': 'vendor keep'})
        text += block('Other', previous) + block('Mainline', previous)
        result = runtime.update_boot_entry(text, previous, previous, full)
        before, after = boot.boot_entries(text), boot.boot_entries(result)
        self.assertEqual(boot.default_label(result), 'Vendor')
        self.assertEqual(after['Vendor'], before['Vendor'])
        self.assertEqual(after['Other'], before['Other'])
        self.assertEqual(after['Mainline'], full)
        self.assertIn('root=UUID=test console=ttyAML0', full['APPEND'])
        self.assertNotIn('systemd.mask=vim4-manager.service', full['APPEND'])
        self.assertEqual(runtime.update_boot_entry(result, full, previous, full), result)

    def test_custom_full_profile_is_never_replaced(self):
        previous = runtime.boot_profile({'APPEND': 'root=test'}, version=CURRENT)
        custom = {**previous, 'APPEND': previous['APPEND'] + ' administrator=keep'}
        with self.assertRaisesRegex(ValueError, 'custom boot arguments'):
            runtime.update_boot_entry('DEFAULT Mainline\n', custom, previous,
                                      runtime.boot_profile({'APPEND': 'root=test'}, ['binder.service'], version=CURRENT))

    def test_framebuffer_console_upgrade_keeps_serial_preferred_and_other_entries(self):
        source = {'APPEND': 'root=test console=ttyS0,921600n8'}
        previous = runtime.boot_profile(source, ['binder.service'], version=CURRENT)
        full = runtime.boot_profile(source, ['binder.service'], framebuffer_console=True, version=CURRENT)
        text = 'DEFAULT Mainline\nLABEL Other\n APPEND administrator=keep\nLABEL Mainline\n'
        text += ''.join(f' {key} {value}\n' for key, value in previous.items())
        result = runtime.update_boot_entry(text, previous, previous, full)
        fields = boot.boot_entries(result)
        self.assertEqual(fields['Other']['APPEND'], 'administrator=keep')
        consoles = [word for word in fields['Mainline']['APPEND'].split() if word.startswith('console=')]
        self.assertEqual(consoles, ['console=tty0', 'console=ttyS0,921600n8'])
        self.assertEqual(runtime.update_boot_entry(result, full, previous, full), result)
