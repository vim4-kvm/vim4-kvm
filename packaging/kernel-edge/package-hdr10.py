#!/usr/bin/env python3
"""Archive a built HDR10 candidate without building, installing or contacting a board."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tomllib


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def commit(path):
    if subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True):
        raise ValueError(f'Candidate source is dirty: {path}')
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def verify_v4l2_plugin(digest, profile):
    recipe = Path(__file__).with_name('sources.toml')
    lock = tomllib.loads(recipe.read_text())['gstreamer']
    key = 'candidate_plugin_sha256' if profile == 'yuv444' else 'native_hdr_plugin_sha256'
    if digest != lock[key]:
        raise ValueError(f'V4L2 plugin hash mismatch for {profile}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v4l2-profile', choices=('native-hdr', 'yuv444'), default='native-hdr',
                        help='Select the registered historical HDR or offline YUV24 plugin')
    for name in ('kernel_payload', 'capture_source', 'onekvm_source', 'capture_plugin',
                 'v4l2_plugin', 'onekvm_binary', 'destination'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    verify_v4l2_plugin(sha(args.v4l2_plugin), args.v4l2_profile)
    kernel = json.loads((args.kernel_payload / 'manifest.json').read_text())
    proof = json.loads((args.kernel_payload / 'runtime-proof.json').read_text())
    if not re.fullmatch(r'7\.3\.0-vim4kvm-hdr10r[1-9][0-9]*\+', kernel['release']):
        raise ValueError('Expected a uniquely named HDR10 kernel candidate')
    if proof['release'] != kernel['release']:
        raise ValueError('Runtime proof release mismatch')
    for name in ('Image', 'vim4.dtb', 'modules.tar.gz'):
        if sha(args.kernel_payload / name) != kernel['artifacts'][name]:
            raise ValueError(f'Kernel payload hash mismatch: {name}')
    if proof['image_sha256'] != kernel['artifacts']['Image']:
        raise ValueError('Runtime proof Image mismatch')
    sources = dict(kernel=kernel['source'], capture=commit(args.capture_source),
                   onekvm=commit(args.onekvm_source))
    for binary in (args.capture_plugin, args.v4l2_plugin, args.onekvm_binary):
        with binary.open('rb') as source:
            header = source.read(64)
        if len(header) != 64 or header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', header, 18)[0] != 183:
            raise ValueError(f'Expected an ARM64 ELF: {binary}')
    archive = args.destination.with_suffix('.tar.gz')
    if args.destination.exists() or archive.exists():
        raise ValueError('Use a new candidate destination and archive name')
    args.destination.mkdir(parents=True)
    plugins = args.destination / 'gstreamer-1.0'
    plugins.mkdir()
    for name in ('Image', 'vim4.dtb', 'modules.tar.gz', 'manifest.json', 'runtime-proof.json'):
        shutil.copy2(args.kernel_payload / name, args.destination / name)
    shutil.copy2(args.capture_plugin, plugins / 'libgstvfmcap.so')
    shutil.copy2(args.v4l2_plugin, plugins / 'libgstvideo4linux2.so')
    shutil.copy2(args.onekvm_binary, args.destination / 'one-kvm')
    recipe = Path(__file__).resolve().parent
    for name in ('hdr10-prepare', 'hdr10-run'):
        shutil.copy2(recipe / name, args.destination / name)
    shutil.copy2(recipe.parents[1] / 'docs/hdr10-remote-73.md', args.destination / 'README.md')
    result = dict(release=kernel['release'], sources=sources,
                  v4l2_profile=args.v4l2_profile,
                  hardware_validated=False, vendor_firmware_included=False,
                  limitations=['native SDR snapshot branch unavailable',
                               '5.15 GPU baseline and 7.3 pixel/performance gates pending',
                               'NanoKVM/JetKVM/PiKVM native Wave5 source not integrated'],
                  sha256={str(p.relative_to(args.destination)): sha(p)
                          for p in sorted(args.destination.rglob('*')) if p.is_file()})
    verify_v4l2_plugin(result['sha256']['gstreamer-1.0/libgstvideo4linux2.so'], args.v4l2_profile)
    (args.destination / 'candidate.json').write_text(json.dumps(result, indent=2) + '\n')
    with tarfile.open(archive, 'x:gz') as output:
        output.add(args.destination, arcname=args.destination.name)
    archive.with_name(archive.name + '.sha256').write_text(sha(archive) + '  ' + archive.name + '\n')
    print(json.dumps(dict(archive=str(archive), sha256=sha(archive), **sources), indent=2))


if __name__ == '__main__':
    main()
