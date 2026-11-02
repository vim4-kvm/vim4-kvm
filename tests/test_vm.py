"""Offline VM safety and lifecycle checks; never contacts OrbStack or a board."""
import argparse
from contextlib import redirect_stdout
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

TOOL = Path(__file__).resolve().parents[1] / 'tools/vm'
loader = importlib.machinery.SourceFileLoader('vm_tool', str(TOOL))
spec = importlib.util.spec_from_loader('vm_tool', loader)
vm = importlib.util.module_from_spec(spec)
loader.exec_module(vm)
SHA = 'a' * 40
CONFIG = dict(kernels=[dict(branch='vim4-kvm-5.15'),
                       dict(branch='vim4-kvm-7.3', revision=SHA,
                            url='https://github.com/example/linux.git')])


class VMTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tool = vm.VM(CONFIG, self.temp.name)
        self.tool.repo.mkdir(parents=True)
        self.tool.git = Mock(return_value='')

    def register(self):
        item = dict(task='task', branch='task', path=str(self.tool.repo) + '-task',
                    build=str(self.tool.build_root / 'task'), start=SHA)
        self.tool.save({'task': item})
        return item

    def test_task_names_and_parser_boundary(self):
        for name in ('../oops', 'A', '', 'x' * 33, 'a/b', 'a b'):
            with self.subTest(name=name), self.assertRaises(argparse.ArgumentTypeError):
                vm.task_name(name)
        self.assertEqual(vm.task_name('x' * 32), 'x' * 32)
        with self.assertRaises(argparse.ArgumentTypeError):
            self.tool.new('vim4-kvm-7.3', SHA)
        self.tool.git.assert_not_called()

    def test_status_warns_about_stale_branches_pin_and_registration(self):
        def git(*args, **kwargs):
            if args[0] == 'for-each-ref':
                return ('refs/heads/vim4-kvm-7.3\t' + SHA + '\t\n'
                        'refs/remotes/origin/vim4-kvm-7.3\t' + 'b' * 40 + '\t')
            if args[:2] == ('rev-list', '--count'):
                return '3'
            if args[0] == 'worktree':
                return f'worktree {self.tool.repo}\0HEAD {SHA}\0branch refs/heads/vim4-kvm-7.3\0\0'
            return ''
        self.tool.git.side_effect = git
        result = self.tool.status()
        self.assertEqual(len(result['warnings']), 4)
        self.assertTrue(any('behind' in w for w in result['warnings']))
        self.assertTrue(any('upstream' in w for w in result['warnings']))
        self.assertTrue(any('pin' in w for w in result['warnings']))
        self.assertIsNone(result['worktrees'][0]['task'])
        self.assertEqual(self.tool.git.call_args_list[0].args[0], 'fetch')

    def test_status_registered_synced_tree_has_no_warnings_and_counts(self):
        item = self.register()
        def git(*args, **kwargs):
            if args[0] == 'for-each-ref':
                return (f'refs/heads/task\t{SHA}\torigin/task\n'
                        f'refs/heads/vim4-kvm-7.3\t{SHA}\torigin/vim4-kvm-7.3\n'
                        f'refs/remotes/origin/vim4-kvm-7.3\t{SHA}\t')
            if args[:2] == ('rev-list', '--count'):
                return '0'
            if args[0] == 'rev-list':
                return '2\t1'
            if args[0] == 'worktree':
                return f'worktree {item["path"]}\0HEAD {SHA}\0branch refs/heads/task\0\0'
            return ''
        self.tool.git.side_effect = git
        result = self.tool.status()
        self.assertEqual(result['warnings'], [])
        self.assertEqual((result['worktrees'][0]['ahead'], result['worktrees'][0]['behind']), (2, 1))

    def test_fetch_failure_is_not_suppressed(self):
        self.tool.git.side_effect = RuntimeError('fetch origin failed: network')
        with self.assertRaisesRegex(RuntimeError, 'fetch origin failed'):
            self.tool.status()

    def test_push_rejects_both_formal_branches_including_full_ref(self):
        for target in ('vim4-kvm-7.3', 'vim4-kvm-5.15', 'refs/heads/vim4-kvm-7.3'):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'protected'):
                self.tool.push('task', target)
        self.tool.git.assert_not_called()

    def test_remove_dirty_even_with_force_and_unpushed_by_default(self):
        self.register()
        for force in (False, True):
            self.tool.git.side_effect = lambda *a, **k: 'task' if a[0] == 'symbolic-ref' else ' M source'
            with self.assertRaisesRegex(ValueError, 'dirty'):
                self.tool.remove('task', force)
        self.tool.git.side_effect = lambda *a, **k: {'symbolic-ref': 'task', 'log': 'abc private fix'}.get(a[0], '')
        with self.assertRaisesRegex(ValueError, 'abc private fix'):
            self.tool.remove('task')
        self.assertIn('task', self.tool.records())
        self.assertFalse(any(c.args[:2] == ('worktree', 'remove') for c in self.tool.git.call_args_list))

    def test_remove_force_removes_registered_task_and_build_only(self):
        item = self.register()
        Path(item['build']).mkdir(parents=True)
        other = self.tool.build_root / 'other'
        other.mkdir()
        self.tool.git.side_effect = lambda *a, **k: {'symbolic-ref': 'task', 'log': 'abc private fix'}.get(a[0], '')
        self.tool.remove('task', True)
        self.assertEqual(self.tool.records(), {})
        self.assertFalse(Path(item['build']).exists())
        self.assertTrue(other.exists())

    def test_unregistered_remove_and_switched_branch_refused(self):
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            self.tool.remove('task', True)
        self.register()
        self.tool.git.return_value = 'someone-else'
        with self.assertRaisesRegex(ValueError, 'expected task'):
            self.tool.remove('task', True)

    def test_new_resolves_sha_and_registers_without_switching_existing_tree(self):
        self.tool.git.side_effect = lambda *a, **k: SHA if a[0] == 'rev-parse' else ''
        with redirect_stdout(io.StringIO()):
            self.tool.new('task', 'origin/vim4-kvm-7.3')
        item = self.tool.records()['task']
        self.assertEqual(item['start'], SHA)
        self.assertTrue(Path(item['build']).is_dir())
        self.tool.git.assert_any_call('worktree', 'add', '-b', 'task', item['path'], SHA)
        with self.assertRaisesRegex(ValueError, 'already exists'), redirect_stdout(io.StringIO()):
            self.tool.new('task', SHA)

    def test_push_credential_is_runtime_helper_only(self):
        self.register()
        self.tool.git = vm.VM.git.__get__(self.tool)
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            output = 'task' if 'symbolic-ref' in argv else SHA if 'rev-parse' in argv else ''
            return subprocess.CompletedProcess(argv, 0, output, '')
        with patch.object(vm.subprocess, 'run', side_effect=run), redirect_stdout(io.StringIO()):
            self.tool.push('task', 'review')
        push = next(argv for argv in calls if 'push' in argv)
        self.assertIn(f'{SHA}:refs/heads/review', push)
        self.assertTrue(any('mac gh auth token' in arg for arg in push))
        self.assertTrue(any('credential.helper=' == arg for arg in push))
        self.assertFalse(any('config' in argv for argv in calls))
        helper = next(arg.removeprefix('credential.helper=') for arg in push
                      if arg.startswith('credential.helper=!'))
        # Execute the actual helper with a fake mac command. The supplied token
        # must reach Git's credential protocol, never the invocation arguments.
        script = 'mac() { printf "%s\\n" "$TEST_TOKEN"; }; ' + helper[1:] + ' get'
        result = subprocess.run(['sh', '-c', script], capture_output=True, text=True,
                                env=dict(os.environ, TEST_TOKEN='ghp_secret'), check=True)
        self.assertIn('password=ghp_secret\n', result.stdout)
        self.assertFalse(any('ghp_secret' in arg for argv in calls for arg in argv))
        self.assertNotIn('ghp_secret', script)
        for operation in ('store', 'erase'):
            script = 'mac() { exit 9; }; ' + helper[1:] + ' ' + operation
            result = subprocess.run(['sh', '-c', script], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, '')

    def test_mac_entry_sends_source_via_orb_without_shared_paths(self):
        with patch.object(vm.sys, 'argv', [str(TOOL), 'status', '--json']), \
                patch.object(vm.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(vm.main(), 0)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ['orb', '-m', 'vim4-build'])
        self.assertEqual(argv[-2:], ['status', '--json'])
        self.assertIn('class VM:', run.call_args.kwargs['input'])

    def test_build_dirs_only_du_local_unowned_children(self):
        item = self.register()
        Path(item['build']).mkdir(parents=True)
        unowned = self.tool.build_root / 'unowned'
        unowned.mkdir()
        (self.tool.build_root / 'mac').symlink_to('/')
        self.tool.run = Mock(return_value=f'42\t{unowned}')
        result = self.tool.build_dirs()
        self.tool.run.assert_called_once_with(['du', '-sx', '--', unowned])
        self.assertEqual(result[0]['size_kib'], 42)
        self.assertEqual(result[0]['path'], str(unowned))


if __name__ == '__main__':
    unittest.main()
