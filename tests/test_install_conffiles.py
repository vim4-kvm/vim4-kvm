"""Component upgrades migrate owned sudoers and retire obsolete privileges."""
import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class SudoersMigrationTest(unittest.TestCase):
    def setUp(self):
        script = (Path(__file__).resolve().parents[1] / 'tools/install-components.sh').read_text()
        python = script.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        function = next(node for node in ast.parse(python).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'unchanged_packaged_sudoers')
        self.run = Mock()
        namespace = dict(Path=Path, hashlib=hashlib, subprocess=SimpleNamespace(run=self.run))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<installer>', 'exec'), namespace)
        self.check = namespace['unchanged_packaged_sudoers']
        self.path = Mock()
        self.path.parent = Path('/etc/sudoers.d')
        self.path.is_symlink.return_value = False
        self.path.__str__ = Mock(return_value='/etc/sudoers.d/vim4-pikvm-media')
        self.path.read_bytes.return_value = b'previous shipped sudoers\n'

    def responses(self, digest):
        self.run.side_effect = [
            SimpleNamespace(returncode=0, stdout='vim4-pikvm: /etc/sudoers.d/vim4-pikvm-media\n'),
            SimpleNamespace(returncode=0, stdout=f' /etc/sudoers.d/vim4-pikvm-media {digest}\n'),
        ]

    def test_upgrade_accepts_previous_shipped_conffile(self):
        self.responses(hashlib.md5(self.path.read_bytes()).hexdigest())
        self.assertTrue(self.check(self.path))

    def test_local_changes_and_unowned_files_remain_protected(self):
        self.responses('0' * 32)
        self.assertFalse(self.check(self.path))
        self.run.side_effect = [SimpleNamespace(returncode=1, stdout='')]
        self.assertFalse(self.check(self.path))
        self.path.is_symlink.return_value = True
        self.run.reset_mock()
        self.assertFalse(self.check(self.path))
        self.run.assert_not_called()


class NanoKVMTailscaleUpgradeTest(unittest.TestCase):
    def test_configure_revokes_legacy_sudoers_and_preserves_tailscale(self):
        source = Path(__file__).resolve().parents[1] / 'packaging/ubuntu/package.py'
        spec = importlib.util.spec_from_file_location('ubuntu_package', source)
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / 'stage'
            # Render the real maintainer script without requiring built assets.
            with patch.object(package, 'copy'), patch.object(package.shutil, 'copytree'):
                package.application(stage)
            script = (stage / 'DEBIAN/postinst').read_text()
            script = re.sub(r'/(?:etc|usr|var|run)/',
                            lambda match: shlex.quote(str(root)) + match[0], script)
            commands = root / 'commands'
            commands.mkdir()
            for name in ('getent', 'install', 'visudo'):
                command = commands / name
                command.write_text('#!/bin/sh\nexit 0\n')
                command.chmod(0o755)
            # Provide the retained helper/sudoers pairs checked by configure.
            for name in ('vim4-video', 'vim4-media', 'vim4-system', 'vim4-update',
                         'vim4-edid', 'vim4-remove-legacy-assistant'):
                package.write(root, 'usr/libexec/' + name, '#!/bin/sh\nexit 0\n', 0o755)
                package.write(root, 'etc/sudoers.d/' + name, 'retained rule\n', 0o440)
            package.write(root, 'etc/sudoers.d/vim4-tailscale', 'old rule\n', 0o440)
            legacy = root / 'etc/sudoers.d/vim4-tailscale'
            preserved = {
                'usr/bin/tailscale': b'existing client',
                'usr/sbin/tailscaled': b'existing daemon',
                'var/lib/tailscale/tailscaled.state': b'existing login state',
            }
            for path, content in preserved.items():
                package.write(root, path, content.decode())
            for _ in range(2):
                subprocess.run(['sh', '-c', script, 'postinst', 'configure'], check=True,
                               env={**os.environ, 'PATH': str(commands) + os.pathsep + os.environ['PATH']})
                self.assertFalse(legacy.exists())
                for path, content in preserved.items():
                    self.assertEqual((root / path).read_bytes(), content)
