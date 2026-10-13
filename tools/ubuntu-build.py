#!/usr/bin/env python3
"""Build the pinned Ubuntu ARM64 environment and component packages in Docker."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'vim4-kvm-builder:ubuntu24.04'


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['environment', 'package', 'verify'])
    parser.add_argument('--version', help='Required for package/verify; explicit component package version')
    parser.add_argument('--allow-dirty', action='store_true', help='Allow development sources, recording dirty state')
    args = parser.parse_args()
    if args.command != 'environment' and not args.version:
        parser.error('package/verify requires --version; no implicit development version is selected')
    if args.command == 'environment':
        subprocess.run(['docker', 'build', '--platform', 'linux/arm64', '-t', IMAGE,
                        str(ROOT / 'packaging/ubuntu')], check=True)
        return
    if Path(args.version).name != args.version or args.version in ('.', '..'):
        raise ValueError('Version must not contain path components')
    destination = ROOT / 'build/packages' / args.version
    if args.command == 'verify':
        metadata = json.loads((destination / 'sources.json').read_text())
        subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/arm64',
                        '--mount', f'type=bind,src={ROOT / "packaging/ubuntu"},dst=/checks,readonly',
                        '--mount', f'type=bind,src={destination},dst=/packages,readonly',
                        metadata['builder'], 'sh', '/checks/verify.sh'], check=True)
        return
    sources = {}
    for name in ('.', 'NanoKVM-Pro', 'gst-plugin-vfmcap', 'gst-plugin-venc'):
        path = ROOT / name
        if Path(output('git', '-C', str(path), 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
            raise ValueError(f'{name} is not an independent repository')
        dirty = bool(output('git', '-C', str(path), 'status', '--porcelain'))
        if dirty and not args.allow_dirty:
            raise ValueError(f'{name} is dirty; commit sources or use --allow-dirty for a development build')
        sources[name] = dict(revision=output('git', '-C', str(path), 'rev-parse', 'HEAD'), dirty=dirty,
                             diff_sha256=hashlib.sha256(output('git', '-C', str(path), 'diff', 'HEAD').encode()).hexdigest())
        files = subprocess.check_output(['git', '-C', str(path), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split(b'\0')
        digest = hashlib.sha256()
        for relative in sorted(set(files) - {b''}):
            file = path / relative.decode()
            digest.update(relative + b'\0')
            if file.is_symlink():
                digest.update(str(file.readlink()).encode())
            elif file.is_file():
                digest.update(file.read_bytes())
            else:
                digest.update(b'<deleted>')
        sources[name]['tree_sha256'] = digest.hexdigest()
    # Resolve the tag before running so metadata describes the actual image used.
    image_id = output('docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE)
    epoch = output('git', 'show', '-s', '--format=%ct', 'HEAD')
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'sources.json').write_text(json.dumps(dict(sources=sources, builder=image_id,
        source_date_epoch=epoch, development=any(s['dirty'] for s in sources.values())), indent=2) + '\n')
    subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/arm64',
                    '--mount', f'type=bind,src={ROOT},dst=/src,readonly',
                    '--mount', f'type=bind,src={destination},dst=/out',
                    '-e', f'PACKAGE_VERSION={args.version}', '-e', f'SOURCE_DATE_EPOCH={epoch}',
                    image_id, 'sh', '/src/packaging/ubuntu/build.sh'], check=True)
    print(f'Packages: {destination}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
