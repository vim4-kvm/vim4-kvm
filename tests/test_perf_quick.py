"""A failed benchmark must release sampling and restore the original service."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quick', ROOT / 'tools/perf-quick.py')
quick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick)


class QuickRecoveryTest(unittest.TestCase):
    def test_native_failure_restores_service_and_sampling(self):
        queue = Mock()
        queue.read.return_value = {'sampling': True}

        def ssh(host, command, **kwargs):
            if command == 'systemctl is-active one-kvm':
                return 'active\n'
            if 'timeout -k' in command:
                raise RuntimeError('injected encoder failure')
            return ''

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(quick.bw, 'require_board', return_value=(queue, 'ticket')), \
                patch.object(quick.bw, 'ssh', side_effect=ssh) as remote, \
                patch.object(quick.subprocess, 'run'):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                quick.native('stock', Path(folder) / 'run')
            self.assertEqual(remote.call_args.args[1], 'sudo -n systemctl start one-kvm')
            self.assertEqual([c.args for c in queue.sampling.call_args_list],
                             [('ticket', True), ('ticket', False)])
