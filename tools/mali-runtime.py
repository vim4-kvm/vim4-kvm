#!/usr/bin/env python3
"""Fetch/install the private r44p0 GPU runtime for the vendor 5.15 kernel.

The vendor library is CLOSED upstream. Fetch its pinned original artifact;
do not add the binary to this repository or replace system graphics libraries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request


SOURCE = ('https://raw.githubusercontent.com/aml-streambox/meson_mali/'
          '51e81d36fccb1340b2dab9490da74ded29f849e1/'
          'lib/arm64/gondul/r44p0/wayland/drm/libMali_r1p0_dmaheap.so')
SHA256 = '536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494'
DESTINATION = Path('/usr/lib/vim4-kvm/gpu')


def verify(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256:
        raise ValueError(f'Unexpected Mali artifact SHA-256: {digest}')


def fetch(directory):
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / 'libMali.so'
    if artifact.exists():
        verify(artifact)
        return
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        candidate = Path(temporary) / 'libMali.so'
        with urllib.request.urlopen(SOURCE, timeout=120) as response, candidate.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        verify(candidate)
        os.replace(candidate, artifact)


def install(directory):
    artifact = directory / 'libMali.so'
    verify(artifact)
    if os.geteuid() != 0:
        raise ValueError('Install requires root')
    if platform.machine() != 'aarch64' or not platform.release().startswith('5.15.'):
        raise ValueError('This runtime requires the AArch64 vendor 5.15 kernel')
    version = subprocess.check_output(['modinfo', '-F', 'version', 'mali_kbase'], text=True).strip()
    if (not version.startswith('r44p0-') or not Path('/dev/mali0').exists()
            or not Path('/sys/module/mali_kbase').is_dir()):
        raise ValueError(f'Expected loaded r44p0 Mali driver and /dev/mali0; found {version}')
    dependencies = subprocess.check_output(['ldd', str(artifact.resolve())], text=True)
    if 'not found' in dependencies:
        raise ValueError(f'Missing runtime dependencies:\n{dependencies}')
    DESTINATION.mkdir(parents=True, exist_ok=True)
    icd = {'file_format_version': '1.0.0', 'ICD': {
        'library_path': str(DESTINATION / 'libMali.so'), 'api_version': '1.3.231'}}
    manifest = {'source': SOURCE, 'sha256': SHA256, 'kernelDriver': version,
                'upstreamLicense': 'CLOSED', 'activation': 'VK_ICD_FILENAMES=' + str(DESTINATION / 'mali.json')}
    # Keep the ICD private: global registration would also select this driver on 7.x.
    with tempfile.TemporaryDirectory(dir=DESTINATION) as temporary:
        staged = Path(temporary)
        (staged / 'libMali.so').write_bytes(artifact.read_bytes())
        (staged / 'mali.json').write_text(json.dumps(icd, indent=2) + '\n')
        (staged / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for path in staged.iterdir():
            path.chmod(0o644)
            os.replace(path, DESTINATION / path.name)
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'install'))
    parser.add_argument('directory', type=Path, help='Downloaded artifact directory')
    args = parser.parse_args()
    try:
        (fetch if args.action == 'fetch' else install)(args.directory)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
