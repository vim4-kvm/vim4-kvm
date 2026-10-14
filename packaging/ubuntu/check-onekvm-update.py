#!/usr/bin/env python3
"""Exercise real dpkg upgrades in the disposable package-check container."""
import hashlib
import http.cookiejar
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.error

assert Path('/.dockerenv').exists() and not Path('/run/systemd/system').exists()
helper = '/tmp/package-check/root/usr/libexec/vim4-onekvm-update'
downloads = Path('/var/lib/one-kvm/updates/download-check')
downloads.mkdir(parents=True)
marker = Path('/var/lib/one-kvm/keep-settings')
marker.write_text('keep existing settings')


def build(version):
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        (stage / 'DEBIAN').mkdir()
        (stage / 'DEBIAN/control').write_text(
            f'Package: vim4-onekvm\nVersion: {version}\nArchitecture: arm64\n'
            'Maintainer: test <test@example.invalid>\nDescription: updater test fixture\n')
        payload = stage / 'opt/vim4-onekvm/update-fixture'
        payload.parent.mkdir(parents=True)
        payload.write_text(version)
        version_file = payload.with_name('version')
        version_file.write_text(version + '\n')
        (stage / 'DEBIAN/md5sums').write_text(
            f'{hashlib.md5(payload.read_bytes()).hexdigest()}  opt/vim4-onekvm/update-fixture\n'
            f'{hashlib.md5(version_file.read_bytes()).hexdigest()}  opt/vim4-onekvm/version\n')
        target = downloads / 'update.deb'
        subprocess.run(['dpkg-deb', '--build', str(stage), str(target)], check=True, stdout=subprocess.DEVNULL)
        return target, hashlib.sha256(target.read_bytes()).hexdigest()


old = '0.0.1+vim4.20261014.1'
new = '0.0.1+vim4.20261014.2'
package, _ = build(old)
subprocess.run(['dpkg', '-i', str(package)], check=True, stdout=subprocess.DEVNULL)
package, checksum = build(new)
subprocess.run(['python3', helper, str(package), checksum, new], check=True)
assert marker.read_text() == 'keep existing settings'
assert Path('/opt/vim4-onekvm/update-fixture').read_text() == new
rejected = subprocess.run(['python3', helper, str(package), checksum, new], capture_output=True)
assert rejected.returncode != 0, 'Same-version installation was accepted'
package, checksum = build(old)
rejected = subprocess.run(['python3', helper, str(package), checksum, old], capture_output=True)
assert rejected.returncode != 0, 'Downgrade was accepted'
print('PASS: real One-KVM package upgrade, configuration preservation, same-version/downgrade rejection')

# Exercise the production HTTP update path, including manifest selection,
# download verification, privileged installation and exec-based restart.
target = '0.0.1+vim4.20261014.3'
package, checksum = build(target)
feed = downloads
(feed / 'onekvm-channels.json').write_text(json.dumps({'stable': target, 'beta': target}))
(feed / 'onekvm-releases.json').write_text(json.dumps({'releases': [{
    'version': target, 'channel': 'stable', 'published_at': '', 'notes': [],
    'artifacts': {'vim4-ubuntu-arm64': {'url': '/update.deb', 'sha256': checksum, 'size': package.stat().st_size}},
}]}))


class FeedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(feed), **kwargs)

    def log_message(self, *_):
        pass


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FeedHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
executable = '/opt/vim4-onekvm/one-kvm'
shutil.copy2('/tmp/package-check/root' + executable, executable)
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def api(path, body=None):
    request = urllib.request.Request('http://127.0.0.1:8080/api/' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    with client.open(request, timeout=5) as response:
        return json.load(response)


with tempfile.TemporaryDirectory() as state, open('/tmp/one-kvm-update-api.log', 'w') as log:
    process = subprocess.Popen([executable, '--data-dir', state], stdout=log, stderr=log,
        env={**os.environ, 'ONE_KVM_UPDATE_BASE_URL': f'http://127.0.0.1:{server.server_port}'})
    try:
        for attempt in range(100):
            try:
                api('setup')
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError('Update test application exited')
                time.sleep(0.05)
        credentials = {'username': 'test-admin', 'password': 'local-fixture-only'}
        api('setup/init', credentials)
        api('auth/login', credentials)
        overview = api('update/overview')
        assert overview['current_version'] == new and overview['target_version'] == target
        assert api('update/upgrade', {'channel': 'stable'})['success']
        for attempt in range(300):
            try:
                status = api('update/status')
                if status['phase'] == 'failed':
                    raise RuntimeError(status['last_error'])
                if status['current_version'] == target and status['phase'] == 'idle':
                    break
            except urllib.error.HTTPError as error:
                if error.code != 401:
                    raise
                api('auth/login', credentials)
            except OSError:
                pass  # The listening socket closes briefly during exec restart.
            time.sleep(0.1)
        else:
            raise RuntimeError('Package update/restart did not complete')
        assert marker.read_text() == 'keep existing settings'
        print('PASS: authenticated update API, manifest/download checks, deb install and restart')
    except Exception:
        print(Path('/tmp/one-kvm-update-api.log').read_text()[-8000:])
        raise
    finally:
        process.terminate()
        process.wait(timeout=15)
        server.shutdown()
