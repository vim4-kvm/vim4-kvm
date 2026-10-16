"""Only unchanged package-owned sudoers may migrate during component upgrades."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


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
