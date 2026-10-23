"""Patch exports must replay exactly, and failed preflight must not allocate worktrees."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('kernel_maintain', ROOT / 'packaging/kernel-edge/maintain.py')
maintain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(maintain)


class KernelMaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'linux'
        self.source.mkdir()
        self.env = dict(os.environ, GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.com',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.com')
        self.git('init', '-q')
        (self.source / 'scripts').mkdir()
        checker = self.source / 'scripts/checkpatch.pl'
        checker.write_text('#!/bin/sh\necho "total: 0 errors, 0 warnings, 0 checks"\n')
        checker.chmod(0o755)
        self.commit('base')
        self.git('tag', 'v7.3-rc7')
        (self.source / 'upstream').write_text('upstream change\n')
        self.commit('upstream change')
        self.git('tag', 'v7.3')
        (self.source / 'driver').write_text('downstream change\n')
        self.commit('downstream change')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args],
                                       env=self.env, text=True).strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)

    def test_export_excludes_upstream_and_reproduces_source_tree(self):
        original = self.git('rev-parse', 'HEAD')
        output = self.root / 'series'
        result = maintain.inventory(SimpleNamespace(source=self.source, output=output,
            head=original, base='v7.3', floor='v7.3-rc7'))
        self.assertEqual(result, 0)
        summary = json.loads((output / 'summary.json').read_text())
        self.assertEqual(summary['patches'], 1)
        self.assertEqual(summary['dispositions']['already-upstream'], 1)
        self.assertTrue(summary['replay_matches_source'])
        self.assertEqual(summary['replay_tree'], self.git('rev-parse', 'HEAD^{tree}'))
        self.assertEqual(self.git('rev-parse', 'HEAD'), original)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_missing_identity_fails_before_worktree_creation(self):
        worktree = self.root / 'candidate'
        real_git = maintain.git

        def missing_identity(source, *args):
            if args == ('var', 'GIT_COMMITTER_IDENT'):
                raise subprocess.CalledProcessError(128, ['git', 'var'])
            return real_git(source, *args)

        with patch.object(maintain, 'git', side_effect=missing_identity):
            with self.assertRaises(subprocess.CalledProcessError):
                maintain.forward(SimpleNamespace(source=self.source, output=self.root / 'forward',
                    head='HEAD', base='v7.3', target='v7.3', branch='maintenance/test', worktree=worktree))
        self.assertFalse(worktree.exists())
        self.assertEqual(len(self.git('worktree', 'list', '--porcelain').split('worktree ')), 2)


if __name__ == '__main__':
    unittest.main()
