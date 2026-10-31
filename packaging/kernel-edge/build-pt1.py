#!/usr/bin/env python3
"""Build and seal the uhd4-based pt1 candidate. Never deploy or select a boot.

Run on Linux ARM64 with an empty output/stage and uhd4.config beside this file.
The display profile does not override GPU nodes and composes with a later kbase
DT selection; this build itself retains uhd4's Panfrost configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    source, output, stage = (p.resolve() for p in (args.source, args.output, args.stage))
    def git(*a):
        return subprocess.check_output(['git', '-C', str(source), *a], text=True).strip()
    subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor',
                    '8bca939d6bbd3', 'HEAD'], check=True)
    if git('status', '--porcelain'):
        raise SystemExit('Require a clean candidate source')
    for p in (output, stage):
        if p == source or source in p.parents or p.exists():
            raise SystemExit('Use new external output and stage directories')
    output.mkdir(parents=True)
    baseline = Path(__file__).with_name('uhd4.config').read_text()
    config = baseline.replace('CONFIG_LOCALVERSION="-vim4kvm-uhd4"',
                              'CONFIG_LOCALVERSION="-vim4kvm-pt1"')
    assert config != baseline
    (output / '.config').write_text(config)
    command = ['make', '-C', str(source), 'O=' + str(output), 'ARCH=arm64',
               'KBUILD_BUILD_USER=vim4-kvm', 'KBUILD_BUILD_HOST=vim4-build']
    subprocess.run(command + ['olddefconfig'], check=True)
    subprocess.run(command + ['-j8', 'Image', 'dtbs', 'modules'], check=True)
    release = (output / 'include/config/kernel.release').read_text().strip()
    if release != '7.3.0-vim4kvm-pt1+':
        raise SystemExit('Unexpected release: ' + release)
    stage.mkdir()
    subprocess.run(command + ['modules_install', 'INSTALL_MOD_STRIP=1',
                              'INSTALL_MOD_PATH=' + str(stage)], check=True)
    modules = stage / 'lib/modules' / release
    for name in ('build', 'source'):
        (modules / name).unlink(missing_ok=True)
    subprocess.run(['depmod', '-b', str(stage), release], check=True)
    boot = stage / 'boot'
    boot.mkdir()
    for src, dest in [('.config', 'config'), ('System.map', 'System.map'),
                      ('arch/arm64/boot/Image', 'Image'),
                      ('arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-passthrough.dtb', 'vim4.dtb')]:
        shutil.copyfile(output / src, boot / dest)
    notes = subprocess.check_output(['readelf', '-n', str(output / 'vmlinux')], text=True)
    manifest = dict(release=release, source=git('rev-parse', 'HEAD'),
                    build_id=re.search(r'Build ID: ([0-9a-f]+)', notes)[1],
                    module_count=sum(p.name.endswith(('.ko', '.ko.xz', '.ko.zst'))
                                     for p in modules.rglob('*')), hardware_verified=False,
                    sha256={str(p.relative_to(stage)): hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
                            for p in sorted(stage.rglob('*')) if p.is_file()})
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = stage.with_suffix('.tar.gz')
    if archive.exists():
        raise SystemExit('Archive already exists')
    subprocess.run(['tar', '-C', str(stage), '-czf', str(archive), '.'], check=True)
    print(json.dumps(dict(release=release, build_id=manifest['build_id'],
                          module_count=manifest['module_count'], archive=str(archive),
                          sha256=hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest())))


if __name__ == '__main__':
    main()
