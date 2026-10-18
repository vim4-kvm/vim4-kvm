"""Gateway upgrades preserve application settings, credentials and YAML comments."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'manager_config', Path(__file__).resolve().parents[1] / 'packaging/ubuntu/manager-config.py')
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)
try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None


class ManagerConfigTest(unittest.TestCase):
    def test_real_postinst_preserves_or_migrates_existing_application_configs(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('ubuntu_package', root / 'packaging/ubuntu/package.py')
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        # The PiKVM packager imports the common packager by its script name.
        with patch.dict(sys.modules, {'package': package}):
            spec = importlib.util.spec_from_file_location('pikvm_package', root / 'packaging/ubuntu/pikvm/package.py')
            pikvm = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pikvm)
        for app, render, config_path, content in [
            ('nanokvm', package.application, 'etc/kvm/server.yaml',
             '# private settings\nhost: 0.0.0.0\nproto: https\nport: {http: 8080, https: 8443}\ncustom: keep\n'),
            ('jetkvm', package.jetkvm, 'var/lib/jetkvm/config.json', '{"localAuthMode":"password","private":"keep"}'),
            ('pikvm', pikvm.pikvm, 'etc/kvmd/override.yaml', 'kvmd: {auth: {enabled: true}}\ncustom: keep\n'),
        ]:
            with self.subTest(application=app), tempfile.TemporaryDirectory() as directory:
                if app == 'pikvm' and not YAML:
                    self.skipTest('PiKVM migration requires ruamel.yaml')
                staging = Path(directory)
                (staging / 'stage/usr/share/kvmd').mkdir(parents=True)
                with patch.object(package, 'copy'), patch.object(pikvm, 'copy'), \
                        patch.object(shutil, 'copytree'), patch.object(Path, 'iterdir', return_value=iter([])):
                    render(staging / 'stage')
                script = (staging / 'stage/DEBIAN/postinst').read_text()
                script = re.sub(r'/(?:etc|usr|var|run|opt)/',
                                lambda match: shlex.quote(str(staging)) + match[0], script)
                commands = staging / 'commands'
                commands.mkdir()
                for name in ('getent', 'install', 'visudo'):
                    package.write(commands, name, '#!/bin/sh\nexit 0\n', 0o755)
                python_wrapper = '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n'
                package.write(commands, 'python3', python_wrapper, 0o755)
                private_python = staging / 'opt/vim4-pikvm/python/bin/python3.14'
                private_python.parent.mkdir(parents=True)
                private_python.write_text(python_wrapper)
                private_python.chmod(0o755)
                for name in ('vim4-video', 'vim4-media', 'vim4-system', 'vim4-update', 'vim4-edid',
                             'vim4-remove-legacy-assistant', 'vim4-jetkvm'):
                    package.write(staging, 'usr/libexec/' + name, '#!/bin/sh\nexit 0\n', 0o755)
                    package.write(staging, 'etc/sudoers.d/' + name, 'fixture rule\n', 0o440)
                if app != 'nanokvm':
                    destination = staging / f'usr/share/vim4-{app}/manager-config.py'
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(root / 'packaging/ubuntu/manager-config.py', destination)
                package.write(staging, config_path, content, 0o600)
                expected = content if app == 'nanokvm' else migration.migrate(content, app)
                for _ in range(2):
                    result = subprocess.run(['sh', '-c', script, 'postinst', 'configure'],
                                            env={**os.environ, 'PATH': str(commands) + os.pathsep + os.environ['PATH']},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((staging / config_path).read_text(), expected)

    def test_jetkvm_preserves_unknown_keys_and_password_hash(self):
        original = dict(localAuthMode='password', local_loopback_only=False, tls_mode='custom',
                        hashedPassword='private hash', future={'nested': [1, 2]}, videoQualityFactor=3)
        updated = migration.migrate(json.dumps(original), 'jetkvm')
        config = json.loads(updated)
        self.assertEqual(config.pop('localAuthMode'), 'noPassword')
        self.assertTrue(config.pop('local_loopback_only'))
        self.assertEqual(config.pop('tls_mode'), '')
        self.assertEqual(config, {key: value for key, value in original.items()
                                  if key not in ('localAuthMode', 'local_loopback_only', 'tls_mode')})
        self.assertEqual(migration.migrate(updated, 'jetkvm'), updated)

    @unittest.skipUnless(YAML, 'requires ruamel.yaml')
    def test_pikvm_manual_auth_override_and_other_settings_survive(self):
        original = ('# user configuration\nkvmd:\n  auth:\n    enabled: true # local login\n'
                    '    totp: {secret: /private/totp}\n  streamer: {h264_bitrate: 30000}\n'
                    'vnc: {enabled: true}\n')
        updated = migration.migrate(original, 'pikvm')
        config = YAML().load(updated)
        self.assertIs(config['kvmd']['auth']['enabled'], False)
        self.assertEqual(config['kvmd']['auth']['totp']['secret'], '/private/totp')
        self.assertEqual(config['kvmd']['streamer']['h264_bitrate'], 30000)
        self.assertTrue(config['vnc']['enabled'])
        self.assertIn('# local login', updated)
        self.assertIn('# user configuration', updated)
        self.assertEqual(migration.migrate(updated, 'pikvm'), updated)

    @unittest.skipUnless(YAML, 'requires ruamel.yaml')
    def test_missing_sections_are_created_and_invalid_configs_are_not_overwritten(self):
        for content in ('# only a comment\n', 'kvmd: {}\n'):
            with self.subTest(content=content):
                updated = migration.migrate(content, 'pikvm')
                self.assertIsInstance(YAML().load(updated), dict)
        for application, content in [('pikvm', 'kvmd: broken\n'),
                                     ('jetkvm', '{invalid')]:
            with self.subTest(application=application), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config'
                path.write_text(content)
                with self.assertRaises(ValueError):
                    migration.migrate_file(path, application)
                self.assertEqual(path.read_text(), content)
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_atomic_upgrade_preserves_permissions_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{"future": "private"}')
            path.chmod(0o600)
            migration.migrate_file(path, 'jetkvm')
            first = path.read_bytes()
            migration.migrate_file(path, 'jetkvm')
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
