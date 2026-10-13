#!/usr/bin/env python3
"""Manage independent source checkouts without modifying existing worktrees."""
import argparse
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent


def run(argv, cwd=ROOT, capture=False):
    return subprocess.run(argv, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def git(path, *args):
    return run(['git', '-C', str(path), *args], capture=True).strip()


def checkout_path(repo):
    path = ROOT / repo['name']
    if Path(repo['name']).name != repo['name'] or repo['name'] in ('.', '..'):
        raise ValueError('Repository names must be direct child directories')
    return path


def check_checkout(path):
    # git inside a non-repository child would otherwise discover the parent repo.
    if path.is_symlink() or not (path / '.git').exists():
        raise ValueError(f'Not an independent checkout: {path}')
    if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
        raise ValueError(f'Unexpected Git root: {path}')


def bootstrap(repos, locked):
    # Check all existing destinations before starting any clone.
    for repo in repos:
        path = checkout_path(repo)
        if path.exists() or path.is_symlink():
            check_checkout(path)
            if locked and (git(path, 'rev-parse', 'HEAD') != repo['revision'] or
                           git(path, 'status', '--porcelain')):
                raise ValueError(f'Locked checkout differs or is dirty: {path}; preserved unchanged')
    for repo in repos:
        path = checkout_path(repo)
        if path.exists():
            print(f'Preserved {repo["name"]}: {git(path, "rev-parse", "--short", "HEAD")}', flush=True)
            continue
        run(['git', 'clone', '--branch', repo['branch'], '--single-branch', repo['url'], str(path)])
        if locked:
            # A failed checkout leaves the clone for inspection; never delete it.
            run(['git', '-C', str(path), 'checkout', '--detach', repo['revision']])


def status(repos):
    for repo in repos:
        path = checkout_path(repo)
        if not path.exists() and not path.is_symlink():
            print(f'{repo["name"]}: missing')
            continue
        check_checkout(path)
        revision = git(path, 'rev-parse', 'HEAD')
        branch = git(path, 'branch', '--show-current') or '(detached)'
        dirty = bool(git(path, 'status', '--porcelain'))
        print(f'{repo["name"]}: {branch} {revision[:12]} '
              f'{"dirty" if dirty else "clean"} '
              f'{"pinned" if revision == repo["revision"] else "differs from pin"}')


def build_plan(target, jobs, kernel_dir, vm):
    output = ROOT / 'build'
    plans = {
        'frontend': [('NanoKVM-Pro/web', 'pnpm install --frozen-lockfile && VITE_PLATFORM=vim4 pnpm build')],
        'capture': [('gst-plugin-vfmcap', 'if [ -f build/build.ninja ]; then meson setup --reconfigure build; else meson setup build; fi && meson compile -C build')],
        'encoder': [('gst-plugin-venc', f'make -C amlvenc PKG_CONFIG=pkg-config CC=gcc -j{jobs}')],
        'server': [('NanoKVM-Pro/server', 'go test -tags vim4 ./... && go build -tags vim4 -o '
                    + shlex.quote(str(output / 'NanoKVM-Server')) + ' .')],
    }
    if target == 'kernel':
        # Kernel stays on Linux; this neither copies sources nor deploys modules.
        make = ('make ARCH=arm64 CC=gcc-12 KBUILD_BUILD_VERSION=1 '
                'KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build')
        command = ('test -f .config && test -d common_drivers/drivers/media/vfm_cap && '
                   f'touch .scmversion && {make} olddefconfig && '
                   f'{make} -j{jobs} Image dtbs modules && '
                   f'{make} M="$PWD/common_drivers/drivers/media/vfm_cap" modules')
        if platform.system() == 'Darwin':
            return [(ROOT, ['orb', '-m', vm, 'bash', '-c',
                            'cd ' + (shlex.quote(kernel_dir) if kernel_dir else '"$HOME/src/linux"')
                            + ' && ' + command])]
        return [(Path(kernel_dir or '~/src/linux').expanduser(), ['bash', '-c', command])]
    targets = ['capture', 'encoder', 'server', 'frontend'] if target == 'all' else [target]
    return [(ROOT / folder, ['bash', '-c', command])
            for item in targets for folder, command in plans[item]]


def build(args, config):
    plan = build_plan(args.target, args.jobs, args.kernel_dir, config['kernel']['vm'])
    for cwd, argv in plan:
        print(f'[{cwd}] {shlex.join(argv)}', flush=True)
    if args.dry_run:
        return
    if args.target in ('all', 'capture', 'encoder', 'server'):
        if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'arm64'):
            raise ValueError('Native backend builds require Linux ARM64 with vendor development libraries; use --dry-run to inspect')
    if args.target == 'kernel' and platform.system() != 'Darwin' and platform.system() != 'Linux':
        raise ValueError('Kernel builds require Linux or the OrbStack VM on macOS')
    for cwd, argv in plan:
        if not cwd.is_dir():
            raise ValueError(f'Missing source directory: {cwd}; run bootstrap first')
        if not shutil.which(argv[0]):
            raise ValueError(f'Missing command: {argv[0]}')
    (ROOT / 'build').mkdir(exist_ok=True)
    for cwd, argv in plan:
        run(argv, cwd=cwd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('bootstrap', help='Clone missing application/driver repos; preserve existing ones')
    init.add_argument('--locked', action='store_true', help='Detach new clones at recorded revisions')
    commands.add_parser('status', help='Show branches, source revisions and dirty state')
    compile_cmd = commands.add_parser('build', help='Build only; never deploy or restart services')
    compile_cmd.add_argument('target', choices=['frontend', 'capture', 'encoder', 'server', 'kernel', 'all'])
    compile_cmd.add_argument('--jobs', type=int, default=10)
    compile_cmd.add_argument('--kernel-dir', help='Kernel path on Linux or inside the VM')
    compile_cmd.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = tomllib.loads((ROOT / 'workspace.toml').read_text())
    if args.command == 'bootstrap':
        bootstrap(config['repos'], args.locked)
    elif args.command == 'status':
        status(config['repos'])
        print('Kernel: external Linux checkout; expected ' + config['kernel']['revision'])
    else:
        if args.jobs < 1:
            parser.error('--jobs must be positive')
        build(args, config)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
