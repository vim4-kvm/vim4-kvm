"""Real-process queue/legacy-lock lifecycle checks, using private temporary locks."""
import fcntl
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/board-queue'
loader = importlib.machinery.SourceFileLoader('queue_tool', str(TOOL))
spec = importlib.util.spec_from_loader('queue_tool', loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


def until(predicate):
    end = time.monotonic() + 8
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError('process did not reach coordinated state')


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue = module.Queue(self.root / 'queue', self.root / 'legacy')
        self.processes = []
        self.tokens = []

    def tearDown(self):
        for token in self.tokens:
            self.queue.release(token)
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        self.temp.cleanup()

    def enqueue(self, who='a', minutes=30, heavy=False):
        token = self.queue.enqueue(who, 'test', minutes, heavy)
        self.tokens.append(token)
        return token

    def start(self, token):
        process = subprocess.Popen([sys.executable, str(TOOL), '--root', str(self.queue.root),
                                   '--legacy-dir', str(self.queue.legacy), '_serve', token],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        return process

    def state(self, token):
        return self.queue.read(token)['state']

    def held(self, token):
        until(lambda: self.state(token) == 'held')

    def test_fifo_even_when_keepers_start_in_reverse_order(self):
        a, b, c = self.enqueue(), self.enqueue('b'), self.enqueue('c')
        self.start(c)
        self.start(b)
        self.start(a)
        self.held(a)
        self.assertEqual(self.state(b), 'queued')
        self.queue.release(a)
        self.held(b)
        self.assertEqual(self.state(c), 'queued')
        self.queue.release(b)
        self.held(c)

    def test_expiry_releases_legacy_locks_and_records_notice(self):
        a, b = self.enqueue(minutes=.003), self.enqueue('b')
        self.start(a)
        self.held(a)
        self.start(b)
        self.held(b)
        self.assertEqual(self.state(a), 'expired')
        self.assertIn('LEASE EXPIRED', (self.queue.root / (a + '.notice')).read_text())
        self.assertIn('timeout-preemption', (self.queue.root / 'history.jsonl').read_text())

    def test_releasing_holder_rejoins_at_tail(self):
        a, b = self.enqueue(), self.enqueue('b')
        self.start(a)
        self.held(a)
        self.queue.release(a)
        again = self.enqueue()
        self.start(again)
        self.start(b)
        self.held(b)
        self.assertEqual(self.state(again), 'queued')

    def test_sampling_drains_heavy_and_blocks_new_heavy(self):
        board, heavy = self.enqueue(), self.enqueue('build', heavy=True)
        self.start(board)
        self.start(heavy)
        self.held(board)
        self.held(heavy)
        with self.queue.guard():
            item = self.queue.read(board)
            item['sampling_requested'] = True
            self.queue.write(item)
        new = self.enqueue('build2', heavy=True)
        self.start(new)
        self.assertFalse(self.queue.read(board)['sampling'])
        self.queue.release(heavy)
        until(lambda: self.queue.read(board)['sampling'])
        self.assertEqual(self.state(new), 'queued')
        self.queue.sampling(board, False)
        self.held(new)

    def test_legacy_flock_and_posix_lockf_block_acquire(self):
        for lock in (fcntl.flock, fcntl.lockf):
            with self.subTest(lock=lock.__name__), (self.queue.legacy / 'vim4-board.lock').open('a+') as fd:
                lock(fd, fcntl.LOCK_EX)
                token = self.enqueue()
                self.start(token)
                until(lambda: self.queue.read(token).get('pid'))
                self.assertEqual(self.state(token), 'queued')
                lock(fd, fcntl.LOCK_UN)
                self.held(token)
                self.queue.release(token)
                until(lambda: self.processes[-1].poll() is not None)

    def test_dead_keeper_does_not_block_successor(self):
        a, b = self.enqueue(), self.enqueue('b')
        process = self.start(a)
        self.held(a)
        process.kill()
        process.wait()
        self.start(b)
        self.held(b)
        self.assertEqual(self.state(a), 'abandoned')

    def run_tool(self, command):
        return [sys.executable, str(TOOL), '--root', str(self.queue.root), '--legacy-dir',
                str(self.queue.legacy), 'run', '--who', 'test', '--purpose', 'test', '--', *command]

    def test_run_failure_releases(self):
        result = subprocess.run(self.run_tool([sys.executable, '-c', 'raise RuntimeError("failure")']),
                                capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        until(lambda: not self.queue.status())

    def test_signal_releases_and_terminates_command(self):
        process = subprocess.Popen(self.run_tool([sys.executable, '-c', 'import signal; signal.pause()']),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        until(lambda: any(i['state'] == 'held' for i in self.queue.status()))
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
        until(lambda: not self.queue.status())

    def test_maximum_window_is_enforced(self):
        with self.assertRaises(ValueError):
            self.enqueue(minutes=31)


if __name__ == '__main__':
    unittest.main()
