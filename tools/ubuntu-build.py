#!/usr/bin/env python3
"""Build the pinned Ubuntu ARM64 environment and component packages in Docker."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'vim4-kvm-builder:ubuntu24.04'
# Component sets and their source repositories. 'all' is the established
# seven-package set used for images; the others are independent releases.
REPOS = {
    'all': ('.', 'NanoKVM', 'gst-plugin-vfmcap', 'gst-plugin-venc', 'kvm', 'One-KVM', 'vim4-manager'),
    'platform': ('.', 'gst-plugin-vfmcap', 'gst-plugin-venc'),
    'capture': ('.', 'gst-plugin-vfmcap'),
    'encoder': ('.', 'gst-plugin-venc'),
    'nanokvm': ('.', 'NanoKVM'),
    'jetkvm': ('.', 'kvm'),
    'onekvm': ('.', 'One-KVM'),
    'manager': ('.', 'vim4-manager'),
    'pikvm': ('.', 'kvmd', 'ustreamer', 'vim4-manager'),
    'pikvm-app': ('.', 'kvmd', 'ustreamer'),
}
# Repository whose GitHub releases carry each set; development versions build on its latest tag.
OWNERS = {'all': '.', 'platform': '.', 'capture': 'gst-plugin-vfmcap', 'encoder': 'gst-plugin-venc',
          'nanokvm': 'NanoKVM', 'jetkvm': 'kvm', 'onekvm': 'One-KVM', 'manager': 'vim4-manager',
          'pikvm': 'kvmd', 'pikvm-app': 'kvmd'}
RELEASE = re.compile(r'\d+\.\d+\.\d+\+vim4\.\d{8}\.\d+', re.ASCII)
# A development build sorts after its base release and before the next one in dpkg and every updater.
DEVELOPMENT = re.compile(r'(?P<base>' + RELEASE.pattern + r')\.dev\.(?P<n>\d+)\.g[0-9a-f]{7,40}(?:\.dirty)?', re.ASCII)
NO_RELEASE = '0.0.0+vim4.00000000.0'


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def release_key(version):
    return [int(part) for part in re.split(r'[.+]', version.replace('vim4.', ''))]


def latest_release(repository, *, allow_cached=True):
    path = str(ROOT / repository)
    # Offline builds fall back to the tags already fetched.
    try:
        fetched = subprocess.run(['git', '-C', path, 'fetch', '--quiet', '--tags', 'origin'], cwd=ROOT,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        offline = fetched.returncode != 0
    except subprocess.TimeoutExpired:
        offline = True
    if offline:
        if not allow_cached:
            raise ValueError(f'Cannot fetch {repository} release tags; refusing to allocate a release version')
        print(f'Warning: cannot fetch {repository} release tags; using cached tags', file=sys.stderr)
    tags = [tag for tag in output('git', '-C', path, 'tag', '--list').splitlines() if RELEASE.fullmatch(tag)]
    return max(tags, key=release_key, default=NO_RELEASE)


def latest_component_release(component, *, allow_cached=True):
    repositories = {OWNERS[component]}
    if component in ('all', 'platform', 'pikvm'):
        # A combined package set must sort after every release it contains.
        repositories.update(set(REPOS[component]) & set(OWNERS.values()))
    return max((latest_release(repo, allow_cached=allow_cached) for repo in sorted(repositories)), key=release_key)


def release_version(date, sequence, previous=NO_RELEASE, *, pikvm=False):
    """Allocate a CI version after existing tags, preserving even/odd image outputs."""
    _, _, _, previous_date, previous_number = release_key(previous)
    if int(date) < previous_date:
        raise ValueError('Release date is earlier than the latest release')
    number = max(2 * sequence, previous_number + 1 if int(date) == previous_date else 0)
    # Image builds run all and pikvm in parallel and need different output paths.
    number += (int(pikvm) - number) % 2
    return f'2.5.1+vim4.{date}.{number}'


def development_version(base, revision, dirty, existing):
    numbers = [int(match['n']) for name in existing if (match := DEVELOPMENT.fullmatch(name)) and match['base'] == base]
    return f'{base}.dev.{max(numbers, default=0) + 1}.g{revision[:7]}' + ('.dirty' if dirty else '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['environment', 'package', 'verify'])
    parser.add_argument('--version', help='Release version x.y.z+vim4.YYYYMMDD.N (clean sources only); '
                        'package without it builds a development version. Required for verify')
    parser.add_argument('--component', choices=list(REPOS), default='all',
                        help='Build the established component set, the platform packages or one application')
    args = parser.parse_args()
    image = 'vim4-pikvm-builder:ubuntu24.04' if args.component in ('pikvm', 'pikvm-app') else IMAGE
    recipes = 'packaging/ubuntu/pikvm' if args.component in ('pikvm', 'pikvm-app') else 'packaging/ubuntu'
    if args.command == 'verify' and not args.version:
        parser.error('verify requires --version; use the version printed by package')
    if args.command == 'package' and args.version and not RELEASE.fullmatch(args.version):
        parser.error('--version must be a release x.y.z+vim4.YYYYMMDD.N; omit it for a development build')
    if args.command == 'environment':
        # The PiKVM builder extends the base builder image.
        for tag, dockerfile in ([(IMAGE, 'packaging/ubuntu/Dockerfile')] if image == IMAGE else
                                [(IMAGE, 'packaging/ubuntu/Dockerfile'), (image, recipes + '/Dockerfile')]):
            subprocess.run(['docker', 'build', '--platform', 'linux/arm64', '-t', tag,
                            '-f', str(ROOT / dockerfile), str(ROOT / 'packaging/ubuntu')], check=True)
        return
    if args.command == 'verify':
        if Path(args.version).name != args.version or args.version in ('.', '..'):
            raise ValueError('Version must not contain path components')
        destination = ROOT / 'build/packages' / args.version
        metadata = json.loads((destination / 'sources.json').read_text())
        if metadata.get('component', 'all') != args.component:
            raise ValueError('Verification component does not match package metadata')
        subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/arm64', '-e', f'COMPONENT={args.component}',
                        '--mount', f'type=bind,src={ROOT / "packaging/ubuntu"},dst=/checks,readonly',
                        '--mount', f'type=bind,src={destination},dst=/packages,readonly',
                        metadata['builder'], 'sh',
                        '/checks/pikvm/verify.sh' if args.component in ('pikvm', 'pikvm-app') else '/checks/verify.sh'], check=True)
        return
    sources = {}
    for name in REPOS[args.component]:
        path = ROOT / name
        if Path(output('git', '-C', str(path), 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
            raise ValueError(f'{name} is not an independent repository')
        dirty = bool(output('git', '-C', str(path), 'status', '--porcelain'))
        if dirty and args.version:
            raise ValueError(f'{name} is dirty; release versions need committed sources, omit --version for a development build')
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
    if args.version:
        version = args.version
    else:
        owner = OWNERS[args.component]
        base = latest_component_release(args.component)
    # Resolve the tag before running so metadata describes the actual image used.
    image_id = output('docker', 'image', 'inspect', '--format', '{{.Id}}', image)
    epoch = output('git', 'show', '-s', '--format=%ct', 'HEAD')
    packages = ROOT / 'build/packages'
    packages.mkdir(parents=True, exist_ok=True)
    # Concurrent local builds share the sequence, even when their commits differ.
    with (packages / '.version.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not args.version:
            version = development_version(base, sources[owner]['revision'],
                                          any(s['dirty'] for s in sources.values()),
                                          [p.name for p in packages.iterdir()])
        destination = packages / version
        destination.mkdir(exist_ok=False)
    (destination / 'sources.json').write_text(json.dumps(dict(sources=sources, builder=image_id, component=args.component,
        source_date_epoch=epoch, version=version, development=not args.version), indent=2) + '\n')
    subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/arm64',
                    '--mount', f'type=bind,src={ROOT},dst=/src,readonly',
                    '--mount', f'type=bind,src={destination},dst=/out',
                    '-e', f'PACKAGE_VERSION={version}', '-e', f'SOURCE_DATE_EPOCH={epoch}',
                    '-e', f'COMPONENT={args.component}',
                    image_id, 'sh', '-c', 'cp "$1" /tmp/vim4-build.sh && exec sh /tmp/vim4-build.sh',
                    'build', '/src/' + recipes + '/build.sh'], check=True)
    print(f'Version: {version}')
    print(f'Packages: {destination}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
