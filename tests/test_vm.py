"""Offline VM safety and lifecycle checks; never contacts OrbStack or a board."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

TOOL = Path(__file__).resolve().parents[1] / 'tools/vm'
loader = importlib.machinery.SourceFileLoader('vm_tool', str(TOOL))
spec = importlib.util.spec_from_loader('vm_tool', loader)
vm = importlib.util.module_from_spec(spec)
loader.exec_module(vm)
SHA = 'a' * 40
CONFIG = dict(kernels=[dict(branch='vim4-kvm-5.15', revision=SHA),
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

    def test_status_warns_about_stale_branches_pin_and_registration(self):
        def git(*args, **kwargs):
            if args[0] == 'for-each-ref':
                return ('refs/heads/vim4-kvm-7.3\t' + SHA + '\t\n'
                        'refs/remotes/origin/vim4-kvm-7.3\t' + 'b' * 40 + '\t')
            if args[:2] == ('rev-list', '--count'):
                return '3'
            if args[0] == 'worktree':
                return (f'worktree {self.tool.repo}\0HEAD {SHA}\0branch refs/heads/vim4-kvm-7.3\0\0'
                        f'worktree {self.tool.repo}-old\0HEAD {SHA}\0detached\0\0')
            return ''
        self.tool.git.side_effect = git
        result = self.tool.status()
        self.assertEqual(len(result['warnings']), 5)
        self.assertIn(f'unregistered worktree: {self.tool.repo}-old', result['warnings'])
        self.assertNotIn(f'unregistered worktree: {self.tool.repo}', result['warnings'])
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
                        f'refs/remotes/origin/task\t{SHA}\t\n'
                        f'refs/remotes/origin/vim4-kvm-5.15\t{SHA}\t\n'
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
        self.tool.config = dict(CONFIG, coordinator=True)
        for target in ('vim4-kvm-7.3', 'vim4-kvm-5.15', 'refs/heads/vim4-kvm-7.3'):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'protected'):
                self.tool.push('task', target)
        self.tool.git.assert_not_called()

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
        self.tool.config = dict(CONFIG, coordinator=True)
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
                                input='protocol=https\nhost=github.com\n\n',
                                env=dict(os.environ, TEST_TOKEN='ghp_secret'), check=True)
        self.assertIn('password=ghp_secret\n', result.stdout)
        self.assertFalse(any('ghp_secret' in arg for argv in calls for arg in argv))
        self.assertNotIn('ghp_secret', script)
        for request in ('protocol=http\nhost=github.com\n\n',
                        'protocol=https\nhost=elsewhere.test\n\n'):
            result = subprocess.run(['sh', '-c', script], input=request,
                                    capture_output=True, text=True,
                                    env=dict(os.environ, TEST_TOKEN='ghp_secret'), check=True)
            self.assertEqual(result.stdout, '')
        for operation in ('store', 'erase'):
            script = 'mac() { exit 9; }; ' + helper[1:] + ' ' + operation
            result = subprocess.run(['sh', '-c', script], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, '')

    def test_mac_entry_sends_source_via_orb_without_shared_paths(self):
        with patch.dict(os.environ, VM_PUSH_COORDINATOR='1'), \
                patch.object(vm.sys, 'argv', [str(TOOL), 'status', '--json']), \
                patch.object(vm.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(vm.main(), 0)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ['orb', '-m', 'vim4-build'])
        self.assertEqual(argv[-2:], ['status', '--json'])
        self.assertIn('class VM:', run.call_args.kwargs['input'])
        config = json.loads(argv[argv.index('_vm') + 1])
        self.assertTrue(config['coordinator'])

    def test_push_requires_explicit_coordinator_switch(self):
        with patch.dict(os.environ, VM_PUSH_COORDINATOR='1'), self.assertRaisesRegex(ValueError, '仅协调者推送'):
            self.tool.push('task', 'review')
        self.tool.git.assert_not_called()
        for value in ('', '0', 'true'):
            with self.subTest(value=value), patch.dict(os.environ, VM_PUSH_COORDINATOR=value), \
                    patch.object(vm.sys, 'argv', [str(TOOL), 'status']), \
                    patch.object(vm.subprocess, 'run', return_value=Mock(returncode=0)) as run:
                vm.main()
            argv = run.call_args.args[0]
            self.assertFalse(json.loads(argv[argv.index('_vm') + 1])['coordinator'])

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


class RealGitTests(unittest.TestCase):
    """Private local remotes reproduce ref/path lifecycle, without any network."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.origin = self.home / 'origin.git'
        self.repo = self.home / 'src/linux-7.3'
        self.repo.mkdir(parents=True)
        self.git('init', '--bare', str(self.origin), cwd=self.home)
        self.git('init', '-b', 'main')
        self.git('commit', '--allow-empty', '-m', 'base')
        self.git('remote', 'add', 'origin', str(self.origin))
        for branch in ('vim4-kvm-5.15', 'vim4-kvm-7.3'):
            self.git('push', 'origin', 'HEAD:refs/heads/' + branch)
        sha = self.git('rev-parse', 'HEAD')
        config = dict(kernels=[dict(branch=k['branch'], revision=sha,
                                    url=CONFIG['kernels'][1]['url']) for k in CONFIG['kernels']])
        self.tool = vm.VM(config, self.home)

    def git(self, *args, cwd=None):
        env = dict(os.environ, GIT_AUTHOR_NAME='VM test', GIT_AUTHOR_EMAIL='vm@example.test',
                   GIT_COMMITTER_NAME='VM test', GIT_COMMITTER_EMAIL='vm@example.test',
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        return subprocess.run(['git', '-C', str(cwd or self.repo), *args],
                              capture_output=True, text=True, check=True, env=env).stdout.rstrip('\n')

    def new(self, task='task'):
        with redirect_stdout(io.StringIO()):
            self.tool.new(task, 'origin/vim4-kvm-7.3')
        return self.tool.records()[task]

    def private_commit(self, item):
        self.git('commit', '--allow-empty', '-m', 'private change', cwd=item['path'])
        return self.git('rev-parse', 'HEAD', cwd=item['path'])

    def test_pruned_origin_and_other_remote_cannot_prove_push(self):
        item = self.new()
        sha = self.private_commit(item)
        self.git('push', 'origin', 'task:refs/heads/review')
        self.tool.fetch()
        self.git('update-ref', 'refs/remotes/upstream/review', sha)
        self.git('update-ref', '-d', 'refs/heads/review', cwd=self.origin)
        with self.assertRaisesRegex(ValueError, 'private change'):
            self.tool.remove('task')
        self.assertTrue(Path(item['path']).exists())
        self.assertNotIn('refs/remotes/origin/review', self.tool.refs())
        self.assertIn('refs/remotes/upstream/review', self.tool.refs())

    def test_status_continues_when_upstream_is_pruned(self):
        item = self.new()
        self.git('push', 'origin', 'task:refs/heads/review')
        self.tool.fetch()
        self.git('branch', '--set-upstream-to=origin/review', 'task')
        self.git('update-ref', '-d', 'refs/heads/review', cwd=self.origin)
        status = self.tool.status()
        tree = next(t for t in status['worktrees'] if t['task'] == 'task')
        self.assertIsNone(tree['ahead'])
        self.assertIsNone(tree['behind'])
        self.assertTrue(any('upstream reference missing: origin/review' in w for w in status['warnings']))
        self.assertEqual(len(status['worktrees']), 2)

    def test_status_checks_both_pins_and_prunes_deleted_formal_ref(self):
        self.git('commit', '--allow-empty', '-m', 'changed 5.15')
        self.git('push', 'origin', 'HEAD:refs/heads/vim4-kvm-5.15')
        status = self.tool.status()
        self.assertTrue(any('pin ' in w and 'origin/vim4-kvm-5.15' in w for w in status['warnings']))
        self.git('update-ref', '-d', 'refs/heads/vim4-kvm-7.3', cwd=self.origin)
        status = self.tool.status()
        self.assertTrue(any('origin/vim4-kvm-7.3: missing' in w for w in status['warnings']))

    def test_remove_leaves_moved_worktree_to_git_refusal(self):
        item = self.new()
        moved = self.home / 'src/moved'
        self.git('worktree', 'move', item['path'], str(moved))
        with self.assertRaisesRegex(RuntimeError, 'branch -D'):
            self.tool.remove('task', True)
        self.assertTrue((moved / '.git').exists())
        self.assertIn('task', self.tool.records())

    def test_remove_dirty_and_private_commits_refused_force_only_skips_commits(self):
        item = self.new()
        dirty = Path(item['path']) / 'untracked'
        dirty.write_text('keep')
        for force in (False, True):
            with self.assertRaisesRegex(ValueError, 'dirty'):
                self.tool.remove('task', force)
        dirty.unlink()
        self.private_commit(item)
        with self.assertRaisesRegex(ValueError, 'private change'):
            self.tool.remove('task')
        self.tool.remove('task', True)
        self.assertEqual(self.tool.records(), {})

    def test_unregistered_and_switched_tasks_are_not_removed(self):
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            self.tool.remove('task', True)
        item = self.new()
        self.git('switch', '-c', 'someone-else', cwd=item['path'])
        with self.assertRaisesRegex(ValueError, 'expected task'):
            self.tool.remove('task', True)
        self.assertTrue(Path(item['path']).exists())

    def test_remove_resumes_after_build_cleanup_failed(self):
        item = self.new()
        with patch.object(vm.shutil, 'rmtree', side_effect=PermissionError('build permission')):
            with self.assertRaises(PermissionError):
                self.tool.remove('task')
        self.assertFalse(Path(item['path']).exists())
        self.assertIn('task', self.tool.records())
        self.tool.remove('task')
        self.assertEqual(self.tool.records(), {})
        self.assertFalse(Path(item['build']).exists())

    def test_remove_resumes_missing_worktree_with_branch_and_checks_commits(self):
        item = self.new()
        self.private_commit(item)
        shutil.rmtree(item['path'])
        with self.assertRaisesRegex(ValueError, 'private change'):
            self.tool.remove('task')
        self.tool.remove('task', True)
        self.assertNotIn('refs/heads/task', self.tool.refs())
        self.assertEqual(self.tool.records(), {})

    def test_registry_transactions_preserve_two_concurrent_creations(self):
        first_read = threading.Event()
        second_lock = threading.Event()
        original_records = self.tool.records
        original_flock = vm.fcntl.flock
        def records():
            value = original_records()
            if threading.current_thread().name.startswith('first'):
                first_read.set()
                self.assertTrue(second_lock.wait(10))
            return value
        def flock(fd, operation):
            if threading.current_thread().name.startswith('second'):
                second_lock.set()
            return original_flock(fd, operation)
        with patch.object(self.tool, 'records', side_effect=records), \
                patch.object(vm.fcntl, 'flock', side_effect=flock), \
                ThreadPoolExecutor(1, thread_name_prefix='first') as first, \
                ThreadPoolExecutor(1, thread_name_prefix='second') as second, redirect_stdout(io.StringIO()):
            a = first.submit(self.tool.new, 'one', 'origin/vim4-kvm-7.3')
            self.assertTrue(first_read.wait(10))
            b = second.submit(self.tool.new, 'two', 'origin/vim4-kvm-7.3')
            a.result(timeout=20)
            b.result(timeout=20)
        self.assertEqual(set(self.tool.records()), {'one', 'two'})


if __name__ == '__main__':
    unittest.main()
