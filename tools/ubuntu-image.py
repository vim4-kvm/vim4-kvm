#!/usr/bin/env python3
"""Build and inspect image files in Linux/OrbStack; never flash a device."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def vm_command(args, capture=False):
    if platform.system() == 'Darwin':
        vm = tomllib.loads((ROOT / 'workspace.toml').read_text())['kernel']['vm']
        args = ['orb', '-m', vm, *args]
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'kernel', 'assemble', 'verify', 'export'])
    parser.add_argument('--name', default='vim4-kvm-ubuntu-0.1.0-dev2')
    parser.add_argument('--components', help='Required for assemble; the version passed to ubuntu-build.py --version')
    parser.add_argument('--pikvm-components', help='Additional PiKVM package version; replaces the manager from --components')
    parser.add_argument('--default-app', choices=['nanokvm', 'jetkvm', 'onekvm', 'pikvm'], default='nanokvm')
    args = parser.parse_args()
    if args.command == 'assemble' and not args.components:
        parser.error('assemble requires --components; use the same version as ubuntu-build.py --version')
    if args.command == 'assemble' and args.default_app == 'pikvm' and not args.pikvm_components:
        parser.error('--default-app pikvm requires --pikvm-components')
    for value in (args.name, args.components, args.pikvm_components):
        if value is None:
            continue
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.~+-]*', value):
            raise ValueError('Names must be single filename components')
    base = ROOT / 'build/downloads/ubuntu-base.img.xz'
    lock = json.loads((ROOT / 'packaging/image/base.lock.json').read_text())
    if args.command == 'fetch':
        base.parent.mkdir(parents=True, exist_ok=True)
        if not base.exists():
            temporary = base.with_suffix('.part')
            with temporary.open('xb') as dest, urllib.request.urlopen(lock['url'], timeout=120) as source:
                shutil.copyfileobj(source, dest)
            with temporary.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != lock['sha256']:
                    raise ValueError(f'Download checksum mismatch; retained {temporary}')
            temporary.rename(base)
        with base.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != lock['sha256']:
                raise ValueError('Existing base checksum mismatch; preserved unchanged')
        print(f'Verified {base}')
        return
    home = vm_command(['bash', '-c', 'printf %s "$HOME"'], capture=True)
    image = f'{home}/image-build/{args.name}.img'
    kernel = ROOT / 'build/packages/kernel'
    if args.command == 'kernel':
        vm_command(['bash', str(ROOT / 'packaging/kernel/package.sh'), f'{home}/src/linux', str(kernel)])
    elif args.command == 'assemble':
        dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
        if dirty:
            raise ValueError('Commit the image recipe before assembling; the image records its commit')
        vm_command(['mkdir', '-p', f'{home}/image-build'])
        vm_command(['sudo', 'bash', str(ROOT / 'packaging/image/assemble.sh'), str(base),
                    str(ROOT / 'build/packages' / args.components), str(kernel), image,
                    str(ROOT / 'build/packages' / args.pikvm_components) if args.pikvm_components else '',
                    args.default_app])
    elif args.command == 'verify':
        vm_command(['sudo', 'bash', str(ROOT / 'packaging/image/verify.sh'), image, str(base)])
    else:
        vm_command(['sudo', 'bash', str(ROOT / 'packaging/image/verify.sh'), image, str(base)])
        destination = ROOT / 'build/images' / args.name
        destination.mkdir(parents=True, exist_ok=False)
        # xz refuses to overwrite an existing compressed output.
        vm_command(['sudo', 'xz', '-T4', '-3', '--check=crc32', '-k', image])
        for suffix in ('.xz', '.packages.txt', '.recipe-commit.txt', '.sha256'):
            vm_command(['cp', image + suffix, str(destination)])
        files = sorted(p for p in destination.iterdir() if p.is_file())
        checksums = []
        for file in files:
            with file.open('rb') as stream:
                checksums.append(hashlib.file_digest(stream, 'sha256').hexdigest() + '  ' + file.name)
        (destination / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
        print(f'Candidate image (not boot-tested): {destination}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
