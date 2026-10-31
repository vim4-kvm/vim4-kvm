import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / 'packaging/hdr2-pq/mcp-screenshot.py'
SPEC = importlib.util.spec_from_file_location('hdr2_mcp', PATH)
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class ScreenshotTransportTest(unittest.TestCase):
    def response(self, body, status=200):
        return subprocess.CompletedProcess([], 0,
            (json.dumps(body) + '\n' + str(status)).encode(), b'')

    def test_credentials_use_stdin_and_each_rpc_starts_new_request(self):
        with patch.object(CLIENT.subprocess, 'run', return_value=self.response(
                {'result': {'content': []}})) as run:
            for serial in (1, 2):
                CLIENT.rpc('http://localhost/api/mcp', 'secret-test-key',
                           'tools/list', {}, serial)
            self.assertEqual(run.call_count, 2)
            for call in run.call_args_list:
                argv = call.args[0]
                self.assertNotIn('secret-test-key', ' '.join(argv))
                self.assertIn(b'secret-test-key', call.kwargs['input'])
                self.assertEqual(argv[argv.index('--config') + 1], '-')

    def test_http_and_protocol_failures_are_not_screenshots(self):
        for response in (self.response({'result': {}}, 401),
                         self.response({'error': {'code': -32000}})):
            with self.subTest(response=response.stdout), \
                    patch.object(CLIENT.subprocess, 'run', return_value=response):
                with self.assertRaises(RuntimeError):
                    CLIENT.rpc('http://localhost/api/mcp', 'key', 'tools/call', {}, 1)


if __name__ == '__main__':
    unittest.main()
