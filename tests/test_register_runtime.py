import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('register_runtime', 'packaging/kernel-edge/register-runtime.py')
boot = load('profile_boot', 'board/vim4boot.py')


class BootProfileTest(unittest.TestCase):
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
