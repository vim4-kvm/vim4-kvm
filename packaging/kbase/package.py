#!/usr/bin/env python3
"""Seal an existing matched uhd5 build; no compilation, installation or blobs."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

KERNEL = '8bca939d6bbd3e4d91e9f23b812e920172c99b3d'
RELEASE = '7.3.0-vim4kvm-uhd5+'


def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'stage', 'candidate', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    k, stage, candidate, output = args.kernel, args.stage, args.candidate, args.output
    assert run('git', '-C', (k/'source').resolve(), 'rev-parse', 'HEAD') == KERNEL
    assert not run('git', '-C', (k/'source').resolve(), 'status', '--porcelain')
    assert (k/'include/config/kernel.release').read_text().strip() == RELEASE
    external = json.loads((candidate/'manifest.json').read_text())
    for name, value in external['kernelFiles'].items():
        assert sha(k/name) == value, name
    modules = stage/'lib/modules'/RELEASE
    expected = {str(Path(n).with_suffix('.ko')) for n in (k/'modules.order').read_text().splitlines()}
    installed = {str(p.relative_to(modules/'kernel')).removesuffix('.xz')
                 for p in (modules/'kernel').rglob('*.ko*')}
    assert expected == installed and len(expected) == 2338
    extras = {'mali_kbase.ko': 'moduleSha256', 'vim4_kbase_heaps.ko': 'heapModuleSha256',
              'governor_vim4.ko': 'governorModuleSha256'}
    assert {p.name for p in (modules/'extra').iterdir()} == set(extras)
    for name, key in extras.items():
        assert sha(modules/'extra'/name) == external[key]
    assert not any(p.is_symlink() for p in modules.rglob('*'))
    ids = {}
    with tempfile.TemporaryDirectory(prefix='uhd5-module-check-') as temporary:
        raw = Path(temporary)/'module.ko'
        for path in sorted(modules.rglob('*.ko*')):
            raw.write_bytes(lzma.decompress(path.read_bytes()) if path.suffix == '.xz' else path.read_bytes())
            assert run('modinfo', '-F', 'vermagic', raw).split()[0] == RELEASE, path
            assert '.BTF ' in run('readelf', '-SW', raw), path
            ids[str(path.relative_to(modules))] = re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', raw))[1]
            if path.is_relative_to(modules/'kernel'):
                original = k/str(path.relative_to(modules/'kernel')).removesuffix('.xz')
                built_id = re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', original))[1]
                assert ids[str(path.relative_to(modules))] == built_id, path
    subprocess.run(['depmod', '-b', str(stage), RELEASE], check=True)
    output.mkdir(parents=True, exist_ok=False)
    for source, name in [(k/'arch/arm64/boot/Image', 'Image'), (k/'.config', 'config'),
                         (k/'Module.symvers', 'Module.symvers'), (candidate/'candidate.dtb', 'vim4.dtb'),
                         (k/'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m0.dtb', 'panfrost.dtb')]:
        shutil.copyfile(source, output/name)
    # Dump without writing back to the retained vmlinux.
    with tempfile.TemporaryDirectory(prefix='uhd5-btf-') as temporary:
        run('objcopy', '--dump-section', '.BTF='+str(output/'vmlinux.btf'), k/'vmlinux', Path(temporary)/'vmlinux')
    run('tar', '-czf', output/'modules.tar.gz', '-C', modules.parent, RELEASE)
    shutil.copytree(candidate/'runtime', output/'runtime')
    shutil.copyfile(candidate/'runtime-files.json', output/'runtime-files.json')
    shutil.copyfile(candidate/'manifest.json', output/'external-manifest.json')
    result = dict(source=KERNEL, release=RELEASE, base_modules=2338, external_modules=3,
                  kernel_build_id=re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', k/'vmlinux'))[1],
                  modules={str(p.relative_to(modules)): sha(p) for p in modules.rglob('*') if p.is_file()},
                  module_build_ids=ids,
                  files={str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file()})
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    run('tar', '-czf', str(output)+'.tar.gz', '-C', output, '.')
    print(json.dumps(dict(manifest=sha(output/'manifest.json'), archive=sha(Path(str(output)+'.tar.gz')))))


if __name__ == '__main__':
    main()
