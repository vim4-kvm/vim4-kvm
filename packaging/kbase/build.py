#!/usr/bin/env python3
"""Offline r44p0 external-module candidate; never installs or contacts hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

VENDOR = '80a07ad5406d57855c996285ae75a50a1b9147ae'
KERNEL = 'f71b5c6289cb3254690e57292327e73514f0715f'
DRIVER = Path('drivers/gpu/arm/midgard')
UAPI = Path('include/uapi/gpu/arm/midgard')
INPUTS = [str(DRIVER), str(UAPI)] + ['include/linux/' + name for name in (
    'memory_group_manager.h', 'mali_arbiter_interface.h',
    'version_compat_defs.h', 'priority_control_manager.h')]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def abi(source, destination):
    """Compare every named ioctl payload's size/alignment and ioctl encoding."""
    contents = subprocess.check_output([
        'cc', '-E', '-dD', '-x', 'c', '-DMALI_USE_CSF=0',
        '-I' + str(source / 'include/uapi'), '-include',
        'gpu/arm/midgard/mali_kbase_ioctl.h', '/dev/null'], text=True)
    types = sorted(set(re.findall(r'\b(struct|union)\s+(kbase_ioctl_\w+)\s*\{', contents)))
    commands = sorted(set(re.findall(r'^#define\s+(KBASE_IOCTL_\w+)\s+_IO', contents, re.M)))
    lines = ['#include <stdio.h>', '#include <stddef.h>',
             '#include <gpu/arm/midgard/mali_kbase_ioctl.h>', 'int main(void) {']
    for kind, name in types:
        lines.append(f'printf("{name} %zu %zu\\n", sizeof({kind} {name}), _Alignof({kind} {name}));')
    for name in commands:
        lines.append(f'printf("{name} %lu\\n", (unsigned long){name});')
    lines += ['return 0;', '}']
    cfile = destination.with_suffix('.c')
    cfile.write_text('\n'.join(lines) + '\n')
    executable = destination.with_suffix('.bin')
    run('cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-DMALI_USE_CSF=0',
        '-I' + str(source / 'include/uapi'), str(cfile), '-o', str(executable))
    with destination.open('w') as output:
        run(str(executable), stdout=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor', required=True, type=Path)
    parser.add_argument('--kernel-source', required=True, type=Path)
    parser.add_argument('--kernel-build', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New empty directory')
    parser.add_argument('--dtb', required=True, type=Path, help='Retained complete DTB; never modified')
    args = parser.parse_args()
    for path, expected in ((args.vendor, VENDOR),):
        actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            parser.error(f'{path}: expected {expected}, found {actual}')
    run('git', '-C', str(args.kernel_source), 'merge-base', '--is-ancestor', KERNEL, 'HEAD')
    # The worktree may commit the isolated DT and trial evidence, never kernel code.
    run('git', '-C', str(args.kernel_source), 'diff', '--exit-code', KERNEL, '--', '.',
        ':!arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-kbase.dts',
        ':!Documentation/gpu/vim4-kbase-trial.rst')
    build_source = (args.kernel_build / 'source').resolve()
    actual = subprocess.check_output(['git', '-C', str(build_source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != KERNEL:
        parser.error('Kernel build directory references a different source revision')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    archive = output / 'source.tar'
    with archive.open('wb') as stream:
        run('git', '-C', str(args.vendor), 'archive', VENDOR, *INPUTS, stdout=stream)
    with tarfile.open(archive) as stream:
        stream.extractall(source, filter='data')
    abi(source, output / 'abi-vendor.txt')
    packaging = Path(__file__).resolve().parent
    patches = (packaging / 'series').read_text().splitlines()
    for name in patches:
        with (packaging / name).open() as patch:
            run('git', 'apply', '-', cwd=source, stdin=patch)
    abi(source, output / 'abi-candidate.txt')
    if (output / 'abi-vendor.txt').read_bytes() != (output / 'abi-candidate.txt').read_bytes():
        raise ValueError('UK payload layout or ioctl encoding changed')
    # All nested UAPI definitions must also remain byte-for-byte unchanged.
    for path in (source / UAPI).rglob('*.h'):
        original = subprocess.check_output(['git', '-C', str(args.vendor), 'show', VENDOR + ':' + str(path.relative_to(source))])
        if path.read_bytes() != original:
            raise ValueError(f'UAPI changed: {path}')
    with (output / 'build.log').open('w') as log:
        run('make', '-C', str(source / DRIVER), 'KDIR=' + str(args.kernel_build.resolve()),
            'CONFIG_MALI_PLATFORM_NAME=vim4', 'CONFIG_MALI_DEVFREQ=y',
            'CONFIG_MALI_GATOR_SUPPORT=n', 'CONFIG_ANDROID=n', 'CONFIG_MALI_KUTF=n',
            'W=1', 'KCFLAGS=-Werror', '-j4', stdout=log, stderr=subprocess.STDOUT)
    module = source / DRIVER / 'mali_kbase.ko'
    info = subprocess.check_output(['modinfo', str(module)], text=True)
    (output / 'modinfo.txt').write_text(info)
    if 'r44p0-01eac0 (UK version 11.39)' not in info:
        raise ValueError('Unexpected module UK version')
    kernel_build = args.kernel_build.resolve()
    release = (kernel_build / 'include/config/kernel.release').read_text().strip()
    staged_module = output / 'stage/lib/modules' / release / 'extra/mali_kbase.ko'
    staged_module.parent.mkdir(parents=True)
    shutil.copyfile(module, staged_module)
    dtb = output / 'candidate.dtb'
    shutil.copyfile(args.dtb, dtb)
    gpu = '/soc/bus@fe000000/gpu@400000'
    compatible = subprocess.check_output(['fdtget', str(dtb), gpu, 'compatible'], text=True)
    if 'arm,mali-bifrost' not in compatible:
        raise ValueError('Expected the retained T7 Panfrost DT')
    run('fdtput', '-t', 's', str(dtb), gpu, 'compatible', 'khadas,vim4-mali-kbase-r44p0')
    run('fdtput', '-d', str(dtb), gpu, 'mali-supply')
    manifest = {'vendor': VENDOR, 'kernel': KERNEL, 'boardTested': False,
                'moduleSha256': sha(module),
                'patches': {name: sha(packaging / name) for name in patches},
                'dtPatchSha256': sha(packaging / '0004-dt-candidate.patch'),
                'abiSha256': sha(output / 'abi-candidate.txt'),
                'retainedDtbSha256': sha(args.dtb), 'candidateDtbSha256': sha(dtb),
                'kernelFiles': {str(p): sha(kernel_build / p) for p in (
                    Path('.config'), Path('Module.symvers'), Path('arch/arm64/boot/Image'))}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
