#!/usr/bin/env python3
"""Map already installed VIM4 SDIO firmware to brcmfmac names.

Does not download firmware, change calibration data, load drivers or connect
to a network. Existing files are accepted only if they contain the same data.
"""
import argparse
import hashlib
import json
from pathlib import Path


FILES = (
    ('fw_bcm43752a2_ag.bin', 'brcmfmac43752-sdio.bin',
     'af7310c6c44da2690ea9f666eea8477a48e906810a1246a5fa207d3788fdf309'),
    ('clm_bcm43752a2_ag.blob', 'brcmfmac43752-sdio.clm_blob',
     'fc0bed644e599e622600431e7e3a11b5816dc7981f1a747c657475a3a761fabf'),
    ('nvram_ap6275s.txt', 'brcmfmac43752-sdio.khadas,vim4.txt',
     'b5f24335121c042aad82bedc4300d0b65d250f978c675c43afea81d028aad5ad'),
)


def prepare(directory):
    created = []
    # Check every input and conflict before creating any alias.
    for source, target, expected in FILES:
        if hashlib.sha256((directory / source).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Unexpected firmware content: {source}')
        destination = directory / target
        if destination.exists() or destination.is_symlink():
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                raise ValueError(f'Conflicting firmware path: {target}')
    try:
        for source, target, _ in FILES:
            destination = directory / target
            if not destination.exists():
                destination.symlink_to(source)
                created.append(destination)
    except OSError:
        for path in reversed(created):
            path.unlink()
        raise
    return [target for _, target, _ in FILES]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-dir', type=Path, default=Path('/lib/firmware/brcm'))
    args = parser.parse_args()
    try:
        print(json.dumps({'aliases': prepare(args.firmware_dir)}))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
