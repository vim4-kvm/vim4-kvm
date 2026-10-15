#!/usr/bin/env python3
"""Write each application's web-update feed next to its package.

Every application is released from its own repository; the board fetches
https://github.com/vim4-kvm/REPO/releases/latest/download/FILE. Tags equal the
package version, so release-relative file names resolve without extra state.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile

RELEASES = 'https://github.com/vim4-kvm/{repo}/releases/download/{version}/{name}'
REPOS = {'vim4-nanokvm': 'NanoKVM', 'vim4-jetkvm': 'kvm', 'vim4-onekvm': 'One-KVM',
         'vim4-pikvm': 'kvmd', 'vim4-manager': 'vim4-manager'}


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm)


def url(package, version, name):
    return RELEASES.format(repo=REPOS[package], version=version, name=name)


def nanokvm(output, deb, version):
    # NanoKVM's updater expects its original bundle: a tarball holding the deb
    # and a JSON record with the deb's base64 SHA-512.
    def record(path):
        return dict(version=version, name=path.name, size=path.stat().st_size,
                    sha512=base64.b64encode(digest(path, 'sha512').digest()).decode())
    archive = output / f'nanokvm_pro_{version}.tar.gz'
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / f'nanokvm_pro_{version}'
        bundle.mkdir()
        (bundle / deb.name).write_bytes(deb.read_bytes())
        (bundle / f'vim4-nanokvm_{version}.json').write_text(json.dumps(record(deb)))
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(bundle, arcname=bundle.name)
    (output / 'nanokvm_pro_latest.json').write_text(json.dumps(record(archive)) + '\n')


def jetkvm(output, deb, version):
    # JetKVM appends /releases to the configured server; the query is ignored.
    (output / 'releases').write_text(json.dumps({
        'appVersion': version, 'appUrl': url('vim4-jetkvm', version, deb.name),
        'appHash': digest(deb).hexdigest(), 'systemVersion': '', 'systemUrl': '', 'systemHash': '',
    }, indent=2) + '\n')


def onekvm(output, deb, version):
    (output / 'onekvm-channels.json').write_text(json.dumps({'stable': version, 'beta': version}) + '\n')
    (output / 'onekvm-releases.json').write_text(json.dumps({'releases': [{
        'version': version, 'channel': 'stable', 'published_at': '',
        'notes': ['VIM4 Ubuntu application package'],
        'artifacts': {'vim4-ubuntu-arm64': {'url': url('vim4-onekvm', version, deb.name),
                                            'sha256': digest(deb).hexdigest(), 'size': deb.stat().st_size}},
    }]}, indent=2) + '\n')


def manager_feed(output, deb, version, package):
    # Read by vim4-manager, which updates packages without a web updater.
    (output / f'{package}-latest.json').write_text(json.dumps({
        'package': package, 'version': version, 'url': url(package, version, deb.name),
        'sha256': digest(deb).hexdigest(), 'size': deb.stat().st_size,
    }, indent=2) + '\n')


def main(output, version):
    for package, write in (('vim4-nanokvm', nanokvm), ('vim4-jetkvm', jetkvm), ('vim4-onekvm', onekvm),
                           ('vim4-pikvm', None), ('vim4-manager', None)):
        deb = output / f'{package}_{version}_arm64.deb'
        if not deb.exists():
            continue
        if write:
            write(output, deb, version)
        manager_feed(output, deb, version, package)


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2])
