import errno
import importlib.util
from pathlib import Path
import unittest
import tempfile
import json
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('parity', Path(__file__).resolve().parents[1] / 'packaging/kbase/default-parity.py')
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


class SnapshotTest(unittest.TestCase):
    def test_timeout_retains_collected_idle_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result'
            with patch('sys.argv', ['parity', '--root', directory, '--output', str(output)]), \
                 patch.object(parity, 'snapshot', return_value={'gpu': '0'}), \
                 patch.object(parity.subprocess, 'check_output', return_value=''), \
                 patch.object(parity.signal, 'signal'), \
                 patch.object(parity.time, 'sleep', side_effect=TimeoutError('external timeout')):
                with self.assertRaises(TimeoutError):
                    parity.main()
            report = json.loads((output / 'result.json').read_text())
            self.assertEqual(len(report['thermal']), 1)
            self.assertEqual(report['thermal'][0]['state'], {'gpu': '0'})
            self.assertEqual(report['error'], 'external timeout')

    def test_unsupported_optional_telemetry_does_not_abort_measurement(self):
        class Entry:
            def __init__(self, name, value):
                self.name, self.value = name, value
            def __str__(self):
                return self.name
            def read_text(self):
                if isinstance(self.value, OSError):
                    raise self.value
                return self.value
        entries = [Entry('gpu/cur_freq', '250000000\n'),
                   Entry('gpu/optional', OSError(errno.EINVAL, 'unsupported'))]
        with patch.object(parity.Path, 'glob', lambda path, pattern: entries if pattern == '*.gpu/cur_freq' else []):
            result = parity.snapshot()
        self.assertEqual(result['gpu/cur_freq'], '250000000')
        self.assertEqual(result['gpu/optional'], {'readError': errno.EINVAL})
