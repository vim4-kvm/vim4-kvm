import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / 'tools/encoder-vbv-run.py'
SPEC = importlib.util.spec_from_file_location('vbv_run', PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class VbvRunRecoveryTests(unittest.TestCase):
    def test_failed_encode_restores_only_previously_active_service(self):
        for was_active in [False, True]:
            with self.subTest(active=was_active), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'evidence'
                args = argparse.Namespace(directory=output, bench=Path('/fixture/bench'),
                                          probe=Path('/fixture/probe'), fixture=Path('/fixture/raw'),
                                          plugin_path='/fixture/plugins')
                failure = subprocess.CalledProcessError(1, ['bench'])
                with mock.patch.object(RUNNER, 'active', side_effect=lambda s: was_active and s == 'one-kvm'), \
                     mock.patch.object(RUNNER, 'service') as service, \
                     mock.patch.object(RUNNER.subprocess, 'run', side_effect=failure), \
                     mock.patch.object(Path, 'read_text', return_value='53000'), \
                     mock.patch.dict(RUNNER.os.environ, {}, clear=True), mock.patch('builtins.print'):
                    with self.assertRaises(subprocess.CalledProcessError):
                        RUNNER.run(args)
                    expected = [mock.call('stop'), mock.call('start')] if was_active else []
                    self.assertEqual(service.call_args_list, expected)
                self.assertTrue((output / 'h264-30000-stock.log').is_file())
                self.assertFalse((output / 'windows.json').exists())

    def test_other_encoder_owner_prevents_service_changes(self):
        with mock.patch.object(RUNNER, 'active', return_value=True), \
             mock.patch.object(RUNNER, 'service') as service:
            with self.assertRaisesRegex(RuntimeError, 'stop nanokvm'):
                RUNNER.run(argparse.Namespace())
            service.assert_not_called()
