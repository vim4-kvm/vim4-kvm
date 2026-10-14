#!/usr/bin/env python3
"""Exercise real dpkg upgrades in the disposable package-check container."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

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
        (stage / 'DEBIAN/md5sums').write_text(
            f'{hashlib.md5(payload.read_bytes()).hexdigest()}  opt/vim4-onekvm/update-fixture\n')
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
