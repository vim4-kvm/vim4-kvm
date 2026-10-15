#!/usr/bin/env python3
"""Check that every generated update feed matches its package byte for byte."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tarfile

directory = Path(sys.argv[1])
debs = {path.name.split('_')[0]: path for path in directory.glob('vim4-*_arm64.deb')}
version = next(iter(debs.values())).name.split('_')[1] if debs else None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def released(name, url):
    expected = f'/releases/download/{version}/{name}'
    assert url.startswith('https://github.com/vim4-kvm/') and url.endswith(expected), url


for package in ('vim4-nanokvm', 'vim4-jetkvm', 'vim4-onekvm', 'vim4-pikvm', 'vim4-manager'):
    deb = debs.get(package)
    feed = directory / f'{package}-latest.json'
    assert bool(deb) == feed.exists(), f'{package}: feed and package must be published together'
    if not deb:
        continue
    record = json.loads(feed.read_text())
    assert record['package'] == package and record['version'] == version
    assert record['sha256'] == sha256(deb) and record['size'] == deb.stat().st_size
    released(deb.name, record['url'])

if 'vim4-nanokvm' in debs:
    latest = json.loads((directory / 'nanokvm_pro_latest.json').read_text())
    archive = directory / latest['name']
    assert latest['version'] == version and latest['size'] == archive.stat().st_size
    assert base64.b64decode(latest['sha512']) == hashlib.sha512(archive.read_bytes()).digest()
    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
        prefix = f'nanokvm_pro_{version}'
        assert names == [prefix, f'{prefix}/vim4-nanokvm_{version}.json', f'{prefix}/{debs["vim4-nanokvm"].name}'], names
        inner = tar.extractfile(f'{prefix}/{debs["vim4-nanokvm"].name}').read()
        metadata = json.load(tar.extractfile(f'{prefix}/vim4-nanokvm_{version}.json'))
        assert metadata['version'] == version and metadata['size'] == len(inner)
        assert metadata['name'] == debs['vim4-nanokvm'].name
        assert base64.b64decode(metadata['sha512']) == hashlib.sha512(inner).digest()
    assert inner == debs['vim4-nanokvm'].read_bytes()

if 'vim4-jetkvm' in debs:
    record = json.loads((directory / 'releases').read_text())
    assert record['appVersion'] == version and record['appHash'] == sha256(debs['vim4-jetkvm'])
    assert record['systemVersion'] == ''
    released(debs['vim4-jetkvm'].name, record['appUrl'])

if 'vim4-onekvm' in debs:
    channels = json.loads((directory / 'onekvm-channels.json').read_text())
    release, = json.loads((directory / 'onekvm-releases.json').read_text())['releases']
    artifact = release['artifacts']['vim4-ubuntu-arm64']
    assert channels == {'stable': version, 'beta': version} and release['version'] == version
    assert artifact['sha256'] == sha256(debs['vim4-onekvm']) and artifact['size'] == debs['vim4-onekvm'].stat().st_size
    released(debs['vim4-onekvm'].name, artifact['url'])

print('PASS: update feeds match their packages')
