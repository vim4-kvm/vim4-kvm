#!/usr/bin/env python3
"""Explicit per-process libmali candidate selection after board acceptance.

No installation, global ICD registration or system library replacement.
The pinned blob lacks GLVND's __egl_Main; EGL/GBM use its direct exports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

SHA256 = '536ee80c17dc5c54e7c6ff029ca43270da8efc3fdc5b3aeb263f364419368494'
VERSION = 'r44p0-01eac0 (UK version 11.39)'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=Path('/usr/lib/vim4-kvm/gpu/libMali.so'))
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('A command is required')
    try:
        version = Path('/sys/module/mali_kbase/version').read_text().strip()
        if version != VERSION or not Path('/dev/mali0').exists():
            raise ValueError('Requires loaded r44p0 UK 11.39 and /dev/mali0')
        library = args.library.resolve(strict=True)
        if hashlib.sha256(library.read_bytes()).hexdigest() != SHA256:
            raise ValueError('libmali hash does not match the accepted UK 11.39 blob')
        env = os.environ.copy()
        for key in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LIBGL_DRIVERS_PATH',
                    '__EGL_VENDOR_LIBRARY_FILENAMES', 'EGL_PLATFORM',
                    'RUSTICL_ENABLE', 'PAN_I_WANT_A_BROKEN_VULKAN_DRIVER'):
            env.pop(key, None)
        with tempfile.TemporaryDirectory(prefix='vim4-kbase-') as directory:
            root = Path(directory)
            (root / 'mali.icd').write_text(str(library) + '\n')
            icd = root / 'mali.json'
            icd.write_text(json.dumps({'file_format_version': '1.0.0', 'ICD': {
                'library_path': str(library), 'api_version': '1.3.231'}}))
            env.update(LD_PRELOAD=str(library), VK_DRIVER_FILES=str(icd),
                       VK_ICD_FILENAMES=str(icd), OCL_ICD_VENDORS=str(root))
            return subprocess.run(command, env=env).returncode
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
