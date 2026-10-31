#!/usr/bin/env python3
"""Build a RAM payload tar.gz; the output directory is packing scratch, not a loose payload.

Arguments: BUNDLE TEMPLATE OUTPUT [VALIDATED_STATIC_INIT]. No board access.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

bundle, template, output = map(Path, sys.argv[1:4])
existing_init = Path(sys.argv[4]) if len(sys.argv) == 5 else None
report = json.loads((bundle / 'manifest.json').read_text())
candidate = json.loads((bundle / 'candidate.json').read_text())
release, build_id = report['release'], report['kernel_build_id']
if release != '7.3.0-vim4kvm-hdr10r3+':
    raise ValueError('This runtime requires the r3 kernel')
for name, expected in candidate['sha256'].items():
    if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != expected:
        raise ValueError('Candidate hash mismatch: ' + name)
config = (template / 'extlinux.conf').read_text()
output.mkdir()
runtime = output / 'runtime'
runtime.mkdir()
recipe = Path(__file__).resolve().parent
for source, name in [('board-runtime', 'vim4-board-runtime'),
                     ('gadget-prepare', 'vim4-mainline-gadget-prepare'),
                     ('one-kvm-edge', 'one-kvm-edge')]:
    shutil.copy2(recipe / source, runtime / name)
for source, name in [('hdr10-prepare', 'vim4-mainline-prepare'),
                     ('hdr10-run', 'hdr10-run'), ('one-kvm', 'one-kvm')]:
    shutil.copy2(bundle / source, runtime / name)
shutil.copytree(bundle / 'gstreamer-1.0', runtime / 'gstreamer-1.0')
prefix = '/var/lib/vim4-kvm/hdr2-unified/' + build_id
launcher = runtime / 'vim4-kvm-run'
launcher.write_text('#!/bin/sh\nset -eu\n'
    'test "${1:-}" = onekvm || exit 2\nshift\n'
    'for icd in /opt/vim4-mesa-26.2.6/share/vulkan/icd.d/*panfrost*.json; do\n'
    ' if [ -r "$icd" ]; then export VK_DRIVER_FILES="$icd"; break; fi\ndone\n'
    'export PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1\n'
    f'exec {prefix}/runtime/hdr10-run "$@"\n')
for path in runtime.iterdir():
    if path.is_file():
        path.chmod(0o755)
for name in ('Image', 'vim4.dtb'):
    shutil.copy2(bundle / name, output / name)
# Keep case-distinct module names inside tar even on a macOS host filesystem.
module_files = {}
with tarfile.open(bundle / 'modules.tar.gz') as archive:
    for member in archive:
        if member.isdir():
            continue
        path = PurePosixPath(member.name)
        if not member.isfile() or path.is_absolute() or '..' in path.parts or path.parts[0] != release:
            raise ValueError('Unsafe module entry: ' + member.name)
        relative = str(PurePosixPath(*path.parts[1:]))
        digest = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        if relative in module_files or report['modules'].get(relative) != digest:
            raise ValueError('Duplicate or mismatched module: ' + relative)
        module_files[relative] = digest
if module_files != report['modules']:
    raise ValueError('Incomplete module archive')
if existing_init is None:
    subprocess.run(['cc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(recipe / 'trial-init.c'), '-o', str(output / 'init')], check=True)
else:
    import importlib.util
    spec = importlib.util.spec_from_file_location('once', recipe.parent / 'kernel-edge/display-once.py')
    once = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(once)
    once.static_arm64(existing_init)
    shutil.copy2(existing_init, output / 'init')
import re
config = re.sub(r'/var/lib/vim4-kvm/hdr2-unified/[0-9a-f]{40}', prefix, config)
if f'init={prefix}/init' not in config:
    raise ValueError('Template lacks the reviewed private PID1 path')
(output / 'extlinux.conf').write_text(config)
manifest = dict(release=release, build_id=build_id, source_commit=report['source'],
                hardware_validated=False,
                sha256={str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(output.rglob('*')) if p.is_file()})
manifest['sha256'].update({'modules/' + release + '/' + name: value for name, value in module_files.items()})
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive = output.with_suffix('.tar.gz')
with tarfile.open(archive, 'x:gz') as package:
    for path in sorted(output.iterdir()):
        package.add(path, arcname=path.name)
    with tarfile.open(bundle / 'modules.tar.gz') as modules:
        for member in modules:
            if member.isdir():
                continue
            data = modules.extractfile(member).read()
            relative = str(PurePosixPath(*PurePosixPath(member.name).parts[1:]))
            if hashlib.sha256(data).hexdigest() != module_files[relative]:
                raise ValueError('Module archive changed while packing')
            member.name = 'modules/' + member.name
            package.addfile(member, io.BytesIO(data))
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name + '.sha256').write_text(digest + '  ' + archive.name + '\n')
print(digest, archive)
