#!/usr/bin/env python3
"""Package an already completed uhd1 build on Linux ARM64; never build Image.

Run inside the Mac vim4-heavy.lock around orb. Output must be a new directory.
The source and O= directory must be the same pair used for build.sh.
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

RELEASE = '7.3.0-vim4kvm-uhd1+'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def run(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def build_id(path):
    return re.search(r'Build ID: ([0-9a-f]+)', run('readelf', '-n', path))[1]


def verify_modules(modules, order):
    expected = {str(Path(name).with_suffix('.ko')) for name in order.read_text().splitlines() if name}
    installed = {str(path.relative_to(modules)).removeprefix('kernel/').removesuffix('.xz')
                 .removesuffix('.zst').removesuffix('.gz') for path in modules.rglob('*.ko*')}
    if not expected or installed != expected:
        raise RuntimeError(f'Module inventory mismatch: missing={sorted(expected - installed)}, '
                           f'unexpected={sorted(installed - expected)}')


def verify_display_profile(output, profile):
    if profile != 'amlogic-t7-a311d2-khadas-vim4-display-m1.dtb':
        return
    if 'CONFIG_DRM_MESON_T7_HANDOFF=y' not in (output / '.config').read_text().splitlines():
        raise RuntimeError('M1 DT requires the built-in T7 handoff driver')
    dtb = output / 'arch/arm64/boot/dts/amlogic' / profile
    for node in ('/chosen/framebuffer@3fdeec00', '/vpu@ff000000'):
        if run('fdtget', dtb, node, 'status') != 'disabled':
            raise RuntimeError(f'M1 requires {node} disabled')
    if run('fdtget', dtb, '/display@ff006840', 'compatible') != 'amlogic,t7-display-handoff':
        raise RuntimeError('M1 DT must use the qualified handoff compatible')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output', 'destination'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--mac', required=True, help='Board ethernet MAC, xx:xx:xx:xx:xx:xx')
    parser.add_argument('--dtb', default='amlogic-t7-a311d2-khadas-vim4-audio-test.dtb',
                        choices=('amlogic-t7-a311d2-khadas-vim4-audio-test.dtb',
                                 'amlogic-t7-a311d2-khadas-vim4-display-m0.dtb',
                                 'amlogic-t7-a311d2-khadas-vim4-display-m1.dtb'),
                        help='Qualified profile; display-m0/m1 require matching U-Boot logo layout')
    parser.add_argument('--release', default=RELEASE)
    args = parser.parse_args()
    release = args.release
    if not re.fullmatch(r'7\.3\.0-vim4kvm-(?:uhd(?:[13]|2(?:-nodebug)?)|npu[0-9]+)\+', release):
        parser.error('Unsupported candidate release')
    source, output, destination = (p.resolve() for p in (args.source, args.output, args.destination))
    assert re.fullmatch(r'[0-9a-f]{40}', args.commit), 'Use the full approved kernel commit'
    assert re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.mac)
    assert run('git', '-C', source, 'rev-parse', 'HEAD') == args.commit
    assert not run('git', '-C', source, 'status', '--porcelain')
    assert output != source and not output.is_relative_to(source)
    report = json.loads((output / 'build.json').read_text())
    assert report['kernel'] == args.commit and report['release'] == release
    for name, expected in report['sha256'].items():
        assert sha(output / name) == expected, name
    assert (output / 'include/config/kernel.release').read_text().strip() == release
    verify_display_profile(output, args.dtb)
    destination.mkdir()  # Refuse stale payloads.
    # Mac shared volumes can fold xt_DSCP/xt_dscp into the same filename.
    # Install on the Linux VM filesystem before writing the portable tarball.
    with tempfile.TemporaryDirectory(prefix='vim4-kernel-modules-') as temporary:
        stage = Path(temporary)
        subprocess.run(['make', '-C', str(source), 'O=' + str(output), 'ARCH=arm64',
                        'modules_install', 'INSTALL_MOD_STRIP=1', 'INSTALL_MOD_PATH=' + str(stage)], check=True)
        modules = stage / 'lib/modules' / release
        verify_modules(modules, output / 'modules.order')
        for name in ('build', 'source'):
            (modules / name).unlink(missing_ok=True)
        subprocess.run(['depmod', '-b', str(stage), release], check=True)
        shutil.copy2(output / 'arch/arm64/boot/Image', destination / 'Image')
        dtb = output / 'arch/arm64/boot/dts/amlogic' / args.dtb
        shutil.copy2(dtb, destination / 'vim4.dtb')
        for prop in ('mac-address', 'local-mac-address'):
            subprocess.run(['fdtput', '-t', 'bx', str(destination / 'vim4.dtb'),
                            '/ethernet@fdc00000', prop, *args.mac.split(':')], check=True)
        subprocess.run(['tar', '-czf', str(destination / 'modules.tar.gz'), '-C',
                        str(stage / 'lib/modules'), release], check=True)
        ids = {}
        # Check every module that will be automatically loaded by the baseline.
        for name, filename in {
            'meson_ir': 'meson-ir', 'rc_khadas': 'rc-khadas', 'ir_nec_decoder': 'ir-nec-decoder',
            'dwmac_meson8b': 'dwmac-meson8b', 'panfrost': 'panfrost', 'brcmfmac': 'brcmfmac',
            'wave5': 'wave5', 't7_hdmirx': 't7-hdmirx', 't7_vdin_test': 't7-vdin-test',
            't7_jpeg': 't7-jpeg', 'crg_udc': 'crg_udc',
        }.items():
            paths = list(modules.rglob(filename + '.ko*'))
            assert len(paths) == 1, (name, paths)
            path = paths[0]
            if path.suffix == '.xz':
                raw = stage / 'module.ko'
                raw.write_bytes(lzma.decompress(path.read_bytes()))
                path = raw
            ids[name] = build_id(path)
        files = {str(p.relative_to(modules)): sha(p) for p in sorted(modules.rglob('*')) if p.is_file()}
        result = dict(source=args.commit, tree=run('git', '-C', source, 'rev-parse', 'HEAD^{tree}'),
                      release=release, kernel_build_id=build_id(output / 'vmlinux'),
                      config_sha256=sha(output / '.config'), modules=files,
                      module_count=len(list(modules.rglob('*.ko*'))), loaded_module_build_ids=ids,
                      artifacts={name: sha(destination / name) for name in ('Image', 'vim4.dtb', 'modules.tar.gz')})
        (destination / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
        subprocess.run(['python3', str(Path(__file__).with_name('register-runtime.py')), 'inventory',
                        '--image', str(destination / 'Image'), '--modules', str(modules),
                        '--output', str(destination / 'runtime-proof.json')], check=True)
    print(json.dumps({k: v for k, v in result.items() if k != 'modules'}, indent=2))


if __name__ == '__main__':
    main()
