#!/usr/bin/env python3
"""Build two integration RAM candidates offline on Linux ARM64.

Caller must already hold the shared heavy lease. This command never queues a
ticket, checks out source, contacts the board or installs into the host root.
Use --help for inputs; baseline is an existing board-window proof, not a query.
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess


RECIPE = Path(__file__).resolve().parent


def run(*args, **kwargs):
    command = list(map(str, args))
    print('+', ' '.join(command), flush=True)
    return subprocess.run(command, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def clean_revision(source, revision):
    if (output('git', '-C', source, 'rev-parse', 'HEAD') != revision or
            output('git', '-C', source, 'status', '--porcelain')):
        raise ValueError('Source must be clean and already at the requested full SHA')


def config_values(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.startswith('CONFIG_'):
            name, value = line.split('=', 1)
            values[name] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            values[line.split()[1]] = 'n'
    return values


def check_config(config, profile):
    actual = config_values(config)
    expected = config_values(RECIPE / 'kernel.config')
    if profile == 'debug':
        # The fragment selects further dependencies; retain the complete
        # generated config and its diff instead of assuming only these change.
        expected = config_values(RECIPE / 'vdec-debug.config') | {
            'CONFIG_KUNIT': 'n', 'CONFIG_FUNCTION_ERROR_INJECTION': 'n'}
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ValueError(f'{profile}: configuration mismatch: {key}')
    if profile == 'production' and sha(config) != sha(RECIPE / 'kernel.config'):
        raise ValueError('Generated production config differs from kernel.config')


def module_identity(path):
    raw = path
    if path.suffix == '.xz':
        raw = path.with_suffix('')
        with raw.open('xb') as stream:
            stream.write(lzma.decompress(path.read_bytes()))
    try:
        if '.BTF' not in output('readelf', '-SW', raw):
            raise ValueError('Missing module BTF: ' + str(path))
        return dict(sha256=sha(path), build_id=build_id(raw),
                    vermagic=output('modinfo', '-F', 'vermagic', raw))
    finally:
        if raw != path:
            raw.unlink()


def build_id(path):
    match = re.search(r'Build ID: ([0-9a-f]{40})\b', output('readelf', '-n', path))
    if not match:
        raise ValueError('Missing GNU build ID: ' + str(path))
    return match[1]


def seal_modules(build, stage, release, make_args, env):
    run('make', *make_args, 'modules_install', 'INSTALL_MOD_STRIP=1',
        'INSTALL_MOD_PATH=' + str(stage), env=env)
    modules = stage / 'lib/modules' / release
    for name in ('build', 'source'):
        (modules / name).unlink(missing_ok=True)
    expected = set((build / 'modules.order').read_text().splitlines())
    installed = {str(p.relative_to(modules / 'kernel')).removesuffix('.xz')
                 for p in (modules / 'kernel').rglob('*.ko*')}
    if installed != expected:
        raise ValueError('Installed base modules differ from modules.order')
    extras = {p.name for p in (modules / 'extra').iterdir()}
    if extras != {'mali_kbase.ko', 'vim4_kbase_heaps.ko', 'governor_vim4.ko'}:
        raise ValueError('Incomplete external module set')
    identities = {}
    for path in sorted(modules.rglob('*.ko*')):
        identity = module_identity(path)
        if identity['vermagic'].split()[0] != release:
            raise ValueError('Mixed module release: ' + str(path))
        identities[str(path.relative_to(modules))] = identity
    run('depmod', '-b', stage, release)
    return modules, identities


def build_profile(args, profile, number, day, env):
    clean_revision(args.source, args.revision)
    target = args.destination / profile
    target.mkdir()
    build = args.build
    localversion = '-vim4-' + day + ('' if number == 1 else '.' + str(number))
    env = dict(env, LOCALVERSION=localversion, KBUILD_BUILD_VERSION='1',
               KBUILD_BUILD_USER='vim4-kvm', KBUILD_BUILD_HOST='vim4-build')
    make_args = ['-C', str(args.source), 'O=' + str(build), 'ARCH=arm64',
                 'CC=gcc', 'LOCALVERSION=' + localversion, 'KBUILD_BUILD_VERSION=1',
                 'KBUILD_BUILD_USER=vim4-kvm', 'KBUILD_BUILD_HOST=vim4-build']
    # Clean before switching profiles: preserve the directory, never reuse a
    # module object built with the other configuration. Packages live outside O=.
    if (build / 'Makefile').exists():
        run('make', *make_args, 'clean', env=env)
    shutil.copy2(RECIPE / 'kernel.config', build / '.config')
    if profile == 'debug':
        run('bash', args.source / 'scripts/kconfig/merge_config.sh', '-m',
            '-O', build, build / '.config', RECIPE / 'vdec-debug.config', env=env)
    run('make', *make_args, 'olddefconfig', env=env)
    check_config(build / '.config', profile)
    run('make', *make_args, '-j' + str(args.jobs), 'W=1', 'Image', 'dtbs', 'modules', env=env)
    release = (build / 'include/config/kernel.release').read_text().strip()
    run('python3', RECIPE.parent / 'kbase/build.py', '--vendor', args.vendor,
        '--kernel-source', args.source, '--kernel-revision', args.revision,
        '--kernel-build', build, '--output', target / 'external',
        '--dtb', build / 'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m0.dtb',
        env=env)
    stage = target / 'external/stage'
    modules, identities = seal_modules(build, stage, release, make_args, env)
    payload = target / 'payload'
    payload.mkdir()
    for origin, name in ((build / 'arch/arm64/boot/Image', 'Image'),
                         (target / 'external/candidate.dtb', 'vim4.dtb'),
                         (build / '.config', 'config'), (build / 'Module.symvers', 'Module.symvers'),
                         (build / 'System.map', 'System.map')):
        shutil.copy2(origin, payload / name)
    for prop in ('mac-address', 'local-mac-address'):
        run('fdtput', '-t', 'bx', payload / 'vim4.dtb', '/ethernet@fdc00000',
            prop, *args.mac.split(':'))
    run('tar', '-czf', payload / 'modules.tar.gz', '-C', modules.parent, release)
    run('objcopy', '--dump-section', '.BTF=' + str(payload / 'vmlinux.btf'),
        build / 'vmlinux', target / 'vmlinux-copy')
    (target / 'vmlinux-copy').unlink()
    artifacts = {p.name: sha(p) for p in payload.iterdir() if p.is_file()}
    base_config = config_values(RECIPE / 'kernel.config')
    actual_config = config_values(build / '.config')
    manifest = dict(source=args.revision,
                    tree=output('git', '-C', args.source, 'rev-parse', 'HEAD^{tree}'),
                    profile=profile, release=release, kernel_build_id=build_id(build / 'vmlinux'),
                    config_sha256=sha(payload / 'config'), ethernet_mac=args.mac,
                    modules={str(p.relative_to(modules)): sha(p)
                             for p in sorted(modules.rglob('*')) if p.is_file()},
                    module_count=len(identities), artifacts=artifacts,
                    compiler=output('gcc', '--version').splitlines()[0],
                    recipe=output('git', '-C', RECIPE, 'rev-parse', 'HEAD'),
                    inputs={str(p.relative_to(RECIPE.parent.parent)): sha(p) for p in
                            (Path(__file__).resolve(), RECIPE / 'kernel.config',
                             RECIPE / 'vdec-debug.config', RECIPE.parent / 'kbase/build.py',
                             RECIPE / 'display-once.py', RECIPE / 'display-once-init.c')},
                    baseline_proof_sha256=sha(args.baseline),
                    config_changes={key: dict(before=base_config.get(key), after=actual_config.get(key))
                                    for key in sorted(base_config.keys() | actual_config.keys())
                                    if base_config.get(key) != actual_config.get(key)},
                    validation='Built offline; hardware regression pending')
    save(payload / 'manifest.json', manifest)
    save(target / 'module-identities.json', identities)
    run('gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
        RECIPE / 'display-once-init.c', '-o', target / 'init')
    run('python3', RECIPE / 'display-once.py', 'prepare', '--payload', payload,
        '--init', target / 'init', '--baseline', args.baseline, '--release', release,
        '--namespace', 'integration-7-3', '--payload-id', profile,
        '--output', target / 'ram')
    clean_revision(args.source, args.revision)
    save(target / 'identity.json', dict(**manifest,
         ram_sha256=sha(target / 'ram/candidate.tar'),
         trial_sha256=sha(target / 'ram/trial.json'),
         module_identities_sha256=sha(target / 'module-identities.json')))
    # The module archive and identity inventory are sealed; avoid retaining a
    # second extracted copy of the entire module tree for each configuration.
    shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', help='Full 40-character integration commit SHA')
    for name in ('source', 'build', 'destination', 'vendor', 'baseline'):
        parser.add_argument('--' + name, required=True, type=lambda p: Path(p).resolve())
    parser.add_argument('--mac', required=True, help='Ethernet MAC from retained baseline proof')
    parser.add_argument('--build-number', type=int, required=True,
                        help='Unused UTC-day production build number; debug uses the next number')
    parser.add_argument('--jobs', type=int, default=8)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.revision):
        parser.error('revision must be a full lowercase commit SHA')
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.mac):
        parser.error('invalid ethernet MAC')
    if args.build_number < 1 or args.jobs < 1:
        parser.error('build number and jobs must be positive')
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('requires Linux ARM64; invoke inside vim4-build under the heavy lease')
    for left, right in ((args.build, args.source), (args.destination, args.source),
                        (args.build, args.destination)):
        if left == right or left.is_relative_to(right) or right.is_relative_to(left):
            parser.error('source, build and destination must be separate directories')
    clean_revision(args.source, args.revision)
    if output('git', '-C', RECIPE, 'status', '--porcelain'):
        parser.error('commit the packaging recipe before building')
    if args.build.exists() and any(args.build.iterdir()):
        if (args.build / 'source').resolve() != args.source:
            parser.error('existing O= directory belongs to a different source')
    # Validate the retained proof before any compilation, without board access.
    baseline = json.loads(args.baseline.read_text())
    if not all(key in baseline for key in ('release', 'build_id', 'files', 'cmdline')):
        parser.error('incomplete baseline proof')
    args.destination.mkdir(parents=True, exist_ok=False)
    args.build.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['SOURCE_DATE_EPOCH'] = output('git', '-C', args.source, 'show', '-s', '--format=%ct', 'HEAD')
    env['KBUILD_BUILD_TIMESTAMP'] = output('date', '-u', '-d', '@' + env['SOURCE_DATE_EPOCH'])
    day = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
    for profile, number in (('production', args.build_number), ('debug', args.build_number + 1)):
        with (args.destination / (profile + '.log')).open('x') as log:
            # Include both subprocess output and the printed command transcript.
            with contextlib.redirect_stdout(log):
                saved = os.dup(1), os.dup(2)
                try:
                    os.dup2(log.fileno(), 1)
                    os.dup2(log.fileno(), 2)
                    build_profile(args, profile, number, day, env)
                finally:
                    os.dup2(saved[0], 1)
                    os.dup2(saved[1], 2)
                    os.close(saved[0])
                    os.close(saved[1])
    removed = 0
    for root in (args.build, args.destination):
        for path in root.rglob('*.o'):
            if path.is_file():
                path.unlink()
                removed += 1
    save(args.destination / 'complete.json', dict(source=args.revision, objects_removed=removed,
         identities={name: sha(args.destination / name / 'identity.json')
                     for name in ('production', 'debug')}))
    print(args.destination / 'complete.json')


if __name__ == '__main__':
    main()
