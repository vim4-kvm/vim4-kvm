"""Direct experimental backend access stays restricted to an explicit local tunnel."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'requires Node.js')
class ManagerLoginTest(unittest.TestCase):
    def test_login(self):
        subprocess.run(['node', '--test', 'tests/manager-login.mjs'], check=True,
                       cwd=ROOT, capture_output=True, text=True)

    def test_local_backend_requires_explicit_loopback_and_preserves_normal_login(self):
        script = r'''
import assert from 'node:assert/strict';
import { loginManager } from './tools/manager-login.mjs';
let calls = 0;
const context = {
  request: { post: async () => { calls++; return { ok: () => true }; } },
  cookies: async () => [{ name: 'vim4_session' }],
};
delete process.env.MANAGER_PASSWORD;
await loginManager(context, 'http://127.0.0.1:18082', { localBackend: true });
assert.equal(calls, 0);
for (const url of ['http://192.168.50.210:8082', 'https://localhost:8082',
                   'http://127.0.0.1.example.com:8082']) {
  await assert.rejects(loginManager(context, url, { localBackend: true }), /loopback/);
}
await assert.rejects(loginManager(context, 'http://127.0.0.1:18082'), /MANAGER_PASSWORD/);
assert.equal(calls, 0);
process.env.MANAGER_PASSWORD = 'isolated-test-fixture';
await loginManager(context, 'http://192.168.50.210:8080');
assert.equal(calls, 1);
'''
        subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                       check=True, capture_output=True, text=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
