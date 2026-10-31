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
KERNEL = '8bca939d6bbd3e4d91e9f23b812e920172c99b3d'
DRIVER = Path('drivers/gpu/arm/midgard')
UAPI = Path('include/uapi/gpu/arm/midgard')
INPUTS = [str(DRIVER), str(UAPI)] + ['include/linux/' + name for name in (
    'memory_group_manager.h', 'mali_arbiter_interface.h',
    'version_compat_defs.h', 'priority_control_manager.h')]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_gpu_cooling(dtb, gpu, next_phandle):
    """Add a frequency map without invalidating existing GPU/fan consumers."""
    existing = subprocess.run(['fdtget', '-t', 'x', str(dtb), gpu, 'phandle'],
                              text=True, capture_output=True)
    gpu_phandle = int(existing.stdout.strip(), 16) if existing.returncode == 0 else next_phandle
    if existing.returncode:
        run('fdtput', '-t', 'x', str(dtb), gpu, 'phandle', format(gpu_phandle, 'x'))
    trip = '/thermal-zones/gpu-thermal/trips/kbase-throttle'
    run('fdtput', '-c', str(dtb), trip)
    run('fdtput', '-t', 's', str(dtb), trip, 'type', 'passive')
    for name, value in {'temperature': 95000, 'hysteresis': 5000,
                        'phandle': next_phandle + 1}.items():
        run('fdtput', '-t', 'x', str(dtb), trip, name, format(value, 'x'))
    cooling = '/thermal-zones/gpu-thermal/cooling-maps/kbase-gpu'
    run('fdtput', '-c', str(dtb), cooling)
    run('fdtput', '-t', 'x', str(dtb), cooling, 'trip', format(next_phandle + 1, 'x'))
    run('fdtput', '-t', 'x', str(dtb), cooling, 'cooling-device',
        format(gpu_phandle, 'x'), '0', '4')


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
    run('python3', str(packaging / 'check-semantics.py'), str(source))
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
    heaps = output / 'heaps'
    run('python3', str(packaging / 'check-heaps.py'))
    shutil.copytree(packaging / 'heaps', heaps)
    with (output / 'heaps-build.log').open('w') as log:
        run('make', '-C', str(args.kernel_build.resolve()), 'M=' + str(heaps),
            'W=1', 'KCFLAGS=-Werror', '-j4', 'modules', stdout=log, stderr=subprocess.STDOUT)
    heap_module = heaps / 'vim4_kbase_heaps.ko'
    governor_build = output / 'dvfs'
    shutil.copytree(packaging / 'dvfs', governor_build)
    with (output / 'governor-build.log').open('w') as log:
        run('make', '-C', str(args.kernel_build.resolve()), 'M=' + str(governor_build),
            'W=1', 'KCFLAGS=-Werror', '-j4', 'modules', stdout=log, stderr=subprocess.STDOUT)
    governor_module = governor_build / 'governor_vim4.ko'
    (output / 'heaps-modinfo.txt').write_text(subprocess.check_output(
        ['modinfo', str(heap_module)], text=True))
    info = subprocess.check_output(['modinfo', str(module)], text=True)
    (output / 'modinfo.txt').write_text(info)
    if 'r44p0-01eac0 (UK version 11.39)' not in info:
        raise ValueError('Unexpected module UK version')
    kernel_build = args.kernel_build.resolve()
    release = (kernel_build / 'include/config/kernel.release').read_text().strip()
    staged_module = output / 'stage/lib/modules' / release / 'extra/mali_kbase.ko'
    staged_module.parent.mkdir(parents=True)
    shutil.copyfile(module, staged_module)
    shutil.copyfile(heap_module, staged_module.with_name(heap_module.name))
    shutil.copyfile(governor_module, staged_module.with_name(governor_module.name))
    runtime_files = {
        'usr/libexec/vim4-board-runtime': packaging.parents[1] / 'board/vim4-board-runtime',
        'usr/libexec/vim4-kvm-run': packaging.parents[1] / 'board/vim4-kvm-run',
        'usr/lib/vim4-kvm/python/vim4gpu.py': packaging / 'run.py',
        'usr/libexec/vim4-mainline-prepare': packaging.parent / 'kernel-edge/one-kvm-edge-prepare',
        'usr/libexec/vim4-mainline-gadget-prepare': packaging.parent / 'kernel-edge/one-kvm-edge-usb-prepare',
    }
    for name, path in runtime_files.items():
        target = output / 'runtime' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o755)
    run('sh', str(runtime_files['usr/libexec/vim4-board-runtime']), 'check-kernel', release)
    (output / 'runtime-files.json').write_text(json.dumps(
        {name: sha(path) for name, path in runtime_files.items()}, indent=2) + '\n')
    probes = output / 'probes'
    probes.mkdir()
    for name in ('run.py', 'clpeak-subset.py', 'dma-profile.py', 'default-parity.py'):
        shutil.copyfile(packaging / name, probes / name)
    dtb = output / 'candidate.dtb'
    shutil.copyfile(args.dtb, dtb)
    gpu = '/soc/bus@fe000000/gpu@400000'
    compatible = subprocess.check_output(['fdtget', str(dtb), gpu, 'compatible'], text=True)
    if 'arm,mali-bifrost' not in compatible:
        raise ValueError('Expected the retained T7 Panfrost DT')
    run('fdtput', '-t', 's', str(dtb), gpu, 'compatible', 'khadas,vim4-mali-kbase-r44p0')
    run('fdtput', '-d', str(dtb), gpu, 'mali-supply')
    run('fdtput', '-d', str(dtb), gpu, 'dma-coherent')
    run('fdtput', '-t', 'x', str(dtb), gpu, 'system-coherency', '0')
    # A separate opt-in CMA pool; preserve every existing peripheral/phandle.
    dts = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(dtb)],
                                  text=True, stderr=subprocess.DEVNULL)
    phandle = max(int(x, 16) for x in re.findall(r'phandle = <0x([0-9a-f]+)>', dts)) + 1
    pool = '/reserved-memory/kbase-gfx-cma'
    run('fdtput', '-c', str(dtb), pool)
    run('fdtput', '-t', 's', str(dtb), pool, 'compatible', 'shared-dma-pool')
    for name, values in {'size': [0, 0x8000000], 'alignment': [0, 0x400000],
                         'alloc-ranges': [0, 0x10000000, 0, 0xe0000000],
                         'phandle': [phandle], 'reusable': []}.items():
        run('fdtput', '-t', 'x', str(dtb), pool, name, *[format(x, 'x') for x in values])
    run('fdtput', '-c', str(dtb), '/kbase-heaps')
    run('fdtput', '-t', 's', str(dtb), '/kbase-heaps', 'compatible', 'khadas,vim4-kbase-heaps')
    run('fdtput', '-t', 'x', str(dtb), '/kbase-heaps', 'memory-region', format(phandle, 'x'))
    # Keep the existing MCU fan map; add an independent GPU frequency map.
    add_gpu_cooling(dtb, gpu, phandle + 1)
    manifest = {'vendor': VENDOR, 'kernel': KERNEL, 'boardTested': False,
                'runtimeManifestSha256': sha(output / 'runtime-files.json'),
                'moduleSha256': sha(module),
                'heapModuleSha256': sha(heap_module),
                'governorModuleSha256': sha(governor_module),
                'governorSources': {path.name: sha(path) for path in (packaging / 'dvfs').iterdir()
                                    if path.is_file()},
                'heapSources': {path.name: sha(path) for path in (packaging / 'heaps').iterdir()
                                if path.is_file()},
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
