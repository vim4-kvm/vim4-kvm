import importlib.util
import json
from pathlib import Path
import sys
import tempfile
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
