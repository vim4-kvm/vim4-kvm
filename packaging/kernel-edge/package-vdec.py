#!/usr/bin/env python3
"""Package a completed, clean vdec4 build offline; run under the heavy lock.

Separate release and deployment inventory: this does not register a KVM runtime.
The deployed baseline and its module directory must remain untouched.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def run(*command):
    return subprocess.check_output(list(map(str, command)), text=True).strip()


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def build_id(path):
    return re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', path))[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output', 'destination'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--mac', required=True)
    args = parser.parse_args()
    source, output, destination = (p.resolve() for p in (args.source, args.output, args.destination))
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.mac):
        parser.error('Invalid ethernet MAC')
    release = (output / 'include/config/kernel.release').read_text().strip()
    if not release.startswith('7.3.0-vim4kvm-vdec4'):
        parser.error('Expected the separate vdec4 build with power opt-in')
    if run('git', '-C', source, 'status', '--porcelain'):
        parser.error('Kernel source must be committed and clean')
    if output == source or output.is_relative_to(source):
        parser.error('Use an independent O= output')
    built = json.loads((output / 'vdec-build.json').read_text())
    if built['source'] != run('git', '-C', source, 'rev-parse', 'HEAD'):
        parser.error('Build stamp does not match the committed source')
    for name, expected in built['sha256'].items():
        if sha(output / name) != expected:
            parser.error('Build stamp mismatch: ' + name)
    destination.mkdir()  # Refuse stale bundles.
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        stage = Path(temporary)
        subprocess.run(['make', '-j8', '-C', str(source), 'O=' + str(output), 'ARCH=arm64',
                        'modules_install', 'INSTALL_MOD_STRIP=1', 'INSTALL_MOD_PATH=' + str(stage)], check=True)
        modules = stage / 'lib/modules' / release
        for name in ('build', 'source'):
            (modules / name).unlink(missing_ok=True)
        subprocess.run(['depmod', '-b', str(stage), release], check=True)
        shutil.copy2(output / 'arch/arm64/boot/Image', destination / 'Image')
        shutil.copy2(output / '.config', destination / 'config')
        dtbs = output / 'arch/arm64/boot/dts/amlogic'
        for target, suffix in (('vim4.dtb', 'vdec-test'), ('baseline-layout.dtb', 'audio-test')):
            path = destination / target
            shutil.copy2(dtbs / ('amlogic-t7-a311d2-khadas-vim4-' + suffix + '.dtb'), path)
            for prop in ('mac-address', 'local-mac-address'):
                subprocess.run(['fdtput', '-t', 'bx', str(path), '/ethernet@fdc00000',
                                prop, *args.mac.split(':')], check=True)
        selected = {}
        for name in ('aml-vdec-drv', 't7-dos', 't7-jpeg', 'wave5'):
            paths = list(modules.rglob(name + '.ko*'))
            if len(paths) != 1:
                raise ValueError('Expected one module: ' + name)
            path = paths[0]
            installed_hash = sha(path)
            if run('modinfo', '-F', 'vermagic', path).split()[0] != release:
                raise ValueError('Mixed vermagic: ' + name)
            if path.suffix == '.xz':
                raw = stage / (name + '.ko')
                raw.write_bytes(lzma.decompress(path.read_bytes()))
                path = raw
            if '.BTF' not in run('readelf', '-SW', path):
                raise ValueError('Missing split BTF: ' + name)
            selected[name] = dict(installed_sha256=installed_hash,
                                  raw_sha256=sha(path), build_id=build_id(path))
        subprocess.run(['tar', '-czf', str(destination / 'modules.tar.gz'), '-C',
                        str(stage / 'lib/modules'), release], check=True)
        report = dict(source=run('git', '-C', source, 'rev-parse', 'HEAD'),
                      tree=run('git', '-C', source, 'rev-parse', 'HEAD^{tree}'),
                      release=release, kernel_build_id=build_id(output / 'vmlinux'),
                      module_count=len(list(modules.rglob('*.ko*'))), selected_modules=selected,
                      config_sha256=sha(output / '.config'), ethernet_mac=args.mac,
                      modules={str(p.relative_to(modules)): sha(p)
                               for p in sorted(modules.rglob('*')) if p.is_file()},
                      artifacts={name: sha(destination / name) for name in
                                 ('Image', 'vim4.dtb', 'baseline-layout.dtb', 'modules.tar.gz', 'config')})
        (destination / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'modules'}, indent=2))


if __name__ == '__main__':
    main()
