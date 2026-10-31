#!/usr/bin/env python3
"""Seal a completed HDR2 kernel build; never install or access a board."""
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

source, output, stage = [Path(arg).resolve() for arg in sys.argv[1:]]
release = (output / 'include/config/kernel.release').read_text().strip()
if not re.fullmatch(r'7\.3\.0-vim4kvm-uhd(?:3-hdr2a[1-9][0-9]*|4(?:r[1-9][0-9]*)?)\+', release):
    raise SystemExit(f'Unexpected release: {release}')
stage.mkdir()  # Never merge a new build into an existing candidate.
subprocess.run(['make', '-C', str(source), f'O={output}', 'ARCH=arm64',
                'modules_install', 'INSTALL_MOD_STRIP=1', f'INSTALL_MOD_PATH={stage}'], check=True)
modules = stage / 'lib/modules' / release
for name in ('build', 'source'):
    path = modules / name
    if path.is_symlink():
        path.unlink()
subprocess.run(['depmod', '-b', str(stage), release], check=True)
boot = stage / 'boot'
boot.mkdir()
for original, target in [('arch/arm64/boot/Image', 'Image'), ('.config', 'config'),
                         ('System.map', 'System.map')]:
    shutil.copy2(output / original, boot / target)
shutil.copytree(output / 'arch/arm64/boot/dts/amlogic', boot / 'amlogic',
                ignore=shutil.ignore_patterns('*.cmd', '.*'))
manifest = {
    'release': release,
    'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
    'validation': 'offline build; PQ/HLG hardware and encoder VUI not validated',
    'modules': len(list(modules.rglob('*.ko*'))),
    'sha256': {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(stage.rglob('*')) if p.is_file() and not p.is_symlink()},
}
(stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
archive = stage.with_suffix('.tar.gz')
if archive.exists():
    raise SystemExit(f'Archive already exists: {archive}')
subprocess.run(['tar', '--sort=name', '--mtime=@1793318400', '--owner=0', '--group=0',
                '-C', str(stage), '-czf', str(archive), '.'], check=True)
print(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive}')
