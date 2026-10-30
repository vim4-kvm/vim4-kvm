#!/usr/bin/env python3
"""Bundle ELF dependency closure and check staged paths, then record file hashes."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def run(*args):
    return subprocess.check_output(args, text=True)


def package(prefix):
    library = prefix / 'lib'
    pending = list(prefix.rglob('*'))
    checked = set()
    system = set()
    while pending:
        path = pending.pop()
        if path.is_symlink() or not path.is_file() or path in checked:
            continue
        if path.open('rb').read(4) != b'\x7fELF':
            continue
        checked.add(path)
        result = subprocess.run(['ldd', str(path)], capture_output=True, text=True,
                                env=dict(os.environ, LD_LIBRARY_PATH=str(library)))
        if 'not found' in result.stdout:
            raise RuntimeError(result.stdout)
        for name, target in re.findall(r'(\S+) => (/\S+)', result.stdout):
            if name in ('libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1'):
                system.add(name)
                continue
            destination = library / name
            if not destination.exists():
                shutil.copyfile(target, destination)
                pending.append(destination)
        relative = '$ORIGIN' if path.parent == library else '$ORIGIN/' + os.path.relpath(library, path.parent)
        subprocess.run(['patchelf', '--set-rpath', relative, str(path)], check=True)
    # Runtime compilation needs clang's resource headers; libclc SPIR-V is static.
    shutil.copytree('/usr/lib/llvm-19/lib/clang', prefix / 'share/clang', dirs_exist_ok=True)
    for path in list((prefix / 'share/vulkan/icd.d').glob('*.json')) + list((prefix / 'share/glvnd/egl_vendor.d').glob('*.json')):
        data = json.loads(path.read_text())
        if 'ICD' in data:
            name = Path(data['ICD']['library_path']).name
            if not (library / name).is_file():
                raise RuntimeError(f'ICD library missing: {name}')
            data['ICD']['library_path'] = '/opt/vim4-mesa-26.2.6/lib/' + name
            path.write_text(json.dumps(data, indent=2) + '\n')
    for path in (prefix / 'etc/OpenCL/vendors').glob('*.icd'):
        name = Path(path.read_text().strip()).name
        if not (library / name).is_file():
            raise RuntimeError(f'OpenCL ICD library missing: {name}')
        path.write_text('/opt/vim4-mesa-26.2.6/lib/' + name + '\n')
    for path in checked:
        result = run('ldd', str(path))
        if 'not found' in result:
            raise RuntimeError(result)
        for target in re.findall(r'=> (/\S+)', result):
            if not target.startswith(str(prefix)) and Path(target).name not in system:
                raise RuntimeError(f'Unbundled dependency: {path}: {target}')
        dynamic = run('readelf', '-d', str(path))
        if '/output' in dynamic or '/opt/rust' in dynamic:
            raise RuntimeError(f'Builder path in dynamic section: {path}')
    files = {str(p.relative_to(prefix)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(prefix.rglob('*')) if p.is_file() and p != prefix / 'manifest.json'}
    (prefix / 'manifest.json').write_text(json.dumps({
        'mesa': '26.2.6', 'source_sha256': 'b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92',
        'elf_count': len(checked), 'system_glibc': sorted(system), 'files': files,
    }, indent=2) + '\n')


if __name__ == '__main__':
    package(Path(sys.argv[1]).resolve())
