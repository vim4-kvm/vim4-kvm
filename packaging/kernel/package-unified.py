#!/usr/bin/env python3
"""Seal the unified kernel, external modules and accepted native HDR userspace offline.

The output is a complete component archive, not a board-window RAM payload.
No installation, board access or licensed firmware inclusion.
"""
import argparse
import datetime
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile
import tarfile
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release import build_contract


def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-lock', type=Path,
                        help='Independent source/release/module-count lock')
    for name in ('kernel', 'stage', 'candidate', 'native', 'wave5-plugin', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    k, stage, candidate, output = args.kernel, args.stage, args.candidate, args.output
    recipe = Path(__file__).resolve().parent
    lock = tomllib.loads((args.candidate_lock or recipe/'sources.toml').read_text())
    revision = lock['kernel']['revision']
    contract = build_contract(lock)
    if contract['date'] != datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'):
        raise ValueError('Package date changed; update sources.toml and rebuild the dated release')
    release = contract['release']
    archive_path = output.parent / ('vim4-kernel-' + release + '.tar.gz')
    if archive_path.exists():
        raise FileExistsError('Package already exists; increment package.build for another same-day build')
    assert sha(k/'.config') == contract['config_sha256']
    assert run('git', '-C', (k/'source').resolve(), 'rev-parse', 'HEAD') == revision
    assert (k/'include/config/kernel.release').read_text().strip() == release
    external = json.loads((candidate/'manifest.json').read_text())
    assert external['kernel'] == revision
    native = json.loads((recipe.parent/'hdr10/native-runtime.json').read_text())
    assert sha(args.native.with_suffix('.tar.gz')) == native['component_archive_sha256']
    with tarfile.open(args.native.with_suffix('.tar.gz')) as archive:
        original = archive.extractfile(args.native.name + '/candidate.json').read()
        assert original == (args.native/'candidate.json').read_bytes()
    accepted = json.loads((args.native/'candidate.json').read_text())
    assert accepted['sources'] == native['sources']
    for name, expected_hash in accepted['sha256'].items():
        assert sha(args.native/name) == expected_hash, name
    assert sha(args.native/'one-kvm') == native['onekvm_binary_sha256']
    assert sha(args.native/'gstreamer-1.0/libgstvideo4linux2.so') == native['gstreamer_v4l2_sha256']
    for name, value in external['kernelFiles'].items():
        assert sha(k/name) == value, name
    modules = stage/'lib/modules'/release
    expected = {str(Path(n).with_suffix('.ko')) for n in (k/'modules.order').read_text().splitlines()}
    installed = {str(p.relative_to(modules/'kernel')).removesuffix('.xz')
                 for p in (modules/'kernel').rglob('*.ko*')}
    assert expected == installed and len(expected) == contract['base_modules']
    extras = {'mali_kbase.ko': 'moduleSha256', 'vim4_kbase_heaps.ko': 'heapModuleSha256',
              'governor_vim4.ko': 'governorModuleSha256'}
    assert {p.name for p in (modules/'extra').iterdir()} == set(extras)
    assert len(extras) == contract['external_modules']
    for name, key in extras.items():
        assert sha(modules/'extra'/name) == external[key]
    assert not any(p.is_symlink() for p in modules.rglob('*'))
    ids = {}
    inventory = {}
    with tempfile.TemporaryDirectory(prefix='uhd5-module-check-') as temporary:
        raw = Path(temporary)/'module.ko'
        for path in sorted(modules.rglob('*.ko*')):
            raw.write_bytes(lzma.decompress(path.read_bytes()) if path.suffix == '.xz' else path.read_bytes())
            vermagic = run('modinfo', '-F', 'vermagic', raw)
            assert vermagic.split()[0] == release, path
            assert '.BTF ' in run('readelf', '-SW', raw), path
            ids[str(path.relative_to(modules))] = re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', raw))[1]
            name = str(path.relative_to(modules))
            inventory[name] = dict(vermagic=vermagic, build_id=ids[name], BTF=True, sha256=sha(path))
    subprocess.run(['depmod', '-b', str(stage), release], check=True)
    output.mkdir(parents=True, exist_ok=False)
    for source, name in [(k/'arch/arm64/boot/Image', 'Image'), (k/'.config', 'config'),
                         (k/'Module.symvers', 'Module.symvers'), (candidate/'candidate.dtb', 'vim4.dtb'),
                         (k/'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-display-m0.dtb', 'panfrost.dtb')]:
        shutil.copyfile(source, output/name)
    # Dump without writing back to the retained vmlinux.
    with tempfile.TemporaryDirectory(prefix='uhd5-btf-') as temporary:
        run('objcopy', '--dump-section', '.BTF='+str(output/'vmlinux.btf'), k/'vmlinux', Path(temporary)/'vmlinux')
    run('tar', '-czf', output/'modules.tar.gz', '-C', modules.parent, release)
    shutil.copytree(candidate/'runtime', output/'runtime')
    shutil.copyfile(candidate/'runtime-files.json', output/'runtime-files.json')
    shutil.copyfile(candidate/'manifest.json', output/'external-manifest.json')
    shutil.copytree(args.native/'gstreamer-1.0', output/'runtime/gstreamer-1.0')
    assert sha(args.wave5_plugin) == '0240de1c003974d97316ff3f73f771a5cc8db2ced1b7330bcbe64c4ba9cbe229'
    shutil.copyfile(args.wave5_plugin, output/'runtime/gstreamer-1.0/libgstvim4wave5.so')
    shutil.copyfile(args.native/'one-kvm', output/'runtime/one-kvm')
    # The Wave5 plugin is a shared dependency; preserve the accepted binary.
    shutil.copyfile(args.native/'candidate.json', output/'native-candidate.json')
    launcher = output/'runtime/usr/libexec/vim4-kvm-run'
    shutil.copyfile(recipe.parents[1]/'board/vim4-kvm-run', launcher)
    shutil.copyfile(recipe.parents[1]/'board/vim4-board-runtime',
                    output/'runtime/usr/libexec/vim4-board-runtime')
    boot_module = output/'runtime/usr/lib/vim4-kvm/python/vim4boot.py'
    boot_module.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(recipe.parents[1]/'board/vim4boot.py', boot_module)
    for source, target in (('one-kvm-edge-prepare', 'vim4-mainline-prepare'),
                           ('one-kvm-edge-usb-prepare', 'vim4-mainline-gadget-prepare')):
        shutil.copyfile(recipe/source, output/'runtime/usr/libexec'/target)
    (output/'module-inventory.json').write_text(json.dumps(inventory, indent=2)+'\n')
    runtime_files = {str(p.relative_to(output/'runtime')): sha(p)
                     for p in (output/'runtime').rglob('*') if p.is_file()}
    (output/'runtime-files.json').write_text(json.dumps(runtime_files, indent=2)+'\n')
    proof = dict(release=release, image_sha256=sha(output/'Image'),
                 module_sha256={str(p.relative_to(modules)): sha(p)
                                for p in modules.rglob('*.ko*')})
    (output/'runtime-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    result = dict(source=revision, **dict(contract, release=release),
                  module_count=len(ids), sources=native['sources'], hardware_validated=False,
                  kernel_build_id=re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', k/'vmlinux'))[1],
                  modules={str(p.relative_to(modules)): sha(p) for p in modules.rglob('*') if p.is_file()},
                  module_build_ids=ids,
                  artifacts={name: sha(output/name) for name in ('Image', 'vim4.dtb', 'modules.tar.gz')},
                  files={str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file()})
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    (output/'candidate.json').write_text(json.dumps(dict(
        sources=native['sources'], hardware_validated=False,
        sha256={str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file()}), indent=2)+'\n')
    run('tar', '-czf', archive_path, '-C', output, '.')
    print(json.dumps(dict(manifest=sha(output/'manifest.json'), archive=sha(archive_path), package=str(archive_path))))


if __name__ == '__main__':
    main()
