#!/usr/bin/env python3
"""Build a private RAM payload from a sealed HDR10 archive directory. No board access."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

bundle, template, output = map(Path, sys.argv[1:])
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
with tarfile.open(bundle / 'modules.tar.gz') as archive:
    archive.extractall(output / 'modules', filter='data')
subprocess.run(['cc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                str(recipe / 'trial-init.c'), '-o', str(output / 'init')], check=True)
import re
config = re.sub(r'/var/lib/vim4-kvm/hdr2-unified/[0-9a-f]{40}', prefix, config)
if f'init={prefix}/init' not in config:
    raise ValueError('Template lacks the reviewed private PID1 path')
(output / 'extlinux.conf').write_text(config)
manifest = dict(release=release, build_id=build_id, source_commit=report['source'],
                hardware_validated=False,
                sha256={str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(output.rglob('*')) if p.is_file()})
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive = output.with_suffix('.tar.gz')
with tarfile.open(archive, 'x:gz') as package:
    for path in sorted(output.iterdir()):
        package.add(path, arcname=path.name)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name + '.sha256').write_text(digest + '  ' + archive.name + '\n')
print(digest, archive)
