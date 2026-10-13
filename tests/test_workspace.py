"""Offline regression checks for preserving independently owned worktrees."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workspace', Path(__file__).resolve().parents[1] / 'tools/workspace.py')
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workspace test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(workspace, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.source = self.root / 'upstream'
        self.git('init', '-b', 'main', str(self.source))
        (self.source / 'file').write_text('first')
        self.git('-C', str(self.source), 'add', 'file')
        self.git('-C', str(self.source), 'commit', '-m', 'fixture')
        self.revision = workspace.git(self.source, 'rev-parse', 'HEAD')
        self.repo = dict(name='child', url=str(self.source), branch='main', revision=self.revision)

    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                   GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
        subprocess.run(['git', *args], env=env, check=True, capture_output=True)

    def test_locked_clone_and_existing_dirty_tree_preserved(self):
        workspace.bootstrap([self.repo], locked=True)
        child = self.root / 'child'
        self.assertEqual(workspace.git(child, 'rev-parse', 'HEAD'), self.revision)
        self.assertEqual(workspace.git(child, 'branch', '--show-current'), '')
        (child / 'file').write_text('user edit')
        workspace.bootstrap([self.repo], locked=False)
        with self.assertRaises(ValueError):
            workspace.bootstrap([self.repo], locked=True)
        self.assertEqual((child / 'file').read_text(), 'user edit')

    def test_preflight_conflict_prevents_partial_clone(self):
        (self.root / 'conflict').mkdir()
        other = dict(self.repo, name='conflict')
        with self.assertRaises(ValueError):
            workspace.bootstrap([self.repo, other], locked=False)
        self.assertFalse((self.root / 'child').exists())

    def test_symlink_and_revision_mismatch_preserved(self):
        child = self.root / 'child'
        child.symlink_to('missing')
        with self.assertRaises(ValueError):
            workspace.bootstrap([self.repo], locked=False)
        self.assertTrue(child.is_symlink())
        child.unlink()
        workspace.bootstrap([self.repo], locked=False)
        with self.assertRaises(ValueError):
            workspace.bootstrap([dict(self.repo, revision='0' * 40)], locked=True)
        self.assertEqual(workspace.git(child, 'rev-parse', 'HEAD'), self.revision)

    def test_mac_backend_rejected_before_commands(self):
        args = type('Args', (), dict(target='all', jobs=2, kernel_dir=None, dry_run=False))()
        with patch.object(workspace.platform, 'system', return_value='Darwin'), patch.object(workspace, 'run') as run:
            with self.assertRaises(ValueError):
                workspace.build(args, {'kernel': {'vm': 'test-vm'}})
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
