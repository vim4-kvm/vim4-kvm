#!/usr/bin/python3
"""Archive bounded brcmfmac crash dumps on 7.x, then release their kernel RAM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

MAX_BYTES = 16 * 1024 * 1024
RETAIN = 2


def save_dump(device, destination, release):
    if not release.startswith('7.'):
        return None
    failing = device / 'failing_device'
    if failing.exists():
        if (failing / 'driver').resolve(strict=True).name != 'brcmfmac':
            return None
    elif not failing.is_symlink() or failing.readlink().name != 'mmc2:0001:1':
        return None
    # VIM4's dedicated SDIO Wi-Fi function can disappear during automatic
    # recovery before udev starts us. The retained symlink still identifies it.
    with (device / 'data').open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Empty or oversized Wi-Fi dump; kernel dump retained')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = destination.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or
            stat.S_IMODE(info.st_mode) != 0o700):
        raise PermissionError('Wi-Fi dump directory must be owned by the collector and mode 0700')
    basename = f'wifi-{time.time_ns()}-{device.name}'
    path = destination / (basename + '.bin')
    with path.open('xb') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    metadata = dict(kernel=release, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    with path.with_suffix('.json').open('x') as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(metadata, output)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    # Never acknowledge a dump before both evidence files are durable.
    directory_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    (device / 'data').write_bytes(b'1')
    dumps = sorted(p for p in destination.iterdir()
                   if re.fullmatch(r'wifi-\d+-devcd\d+\.bin', p.name))
    for old in dumps[:-RETAIN]:
        old.unlink()
        old.with_suffix('.json').unlink(missing_ok=True)
    return dict(path=str(path), **metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('device')
    args = parser.parse_args()
    if not re.fullmatch(r'devcd\d+', args.device) or os.geteuid() != 0:
        parser.error('Requires root and one devcdN device name')
    try:
        result = save_dump(Path('/sys/class/devcoredump') / args.device,
                           Path('/var/lib/vim4-edge-wifi-dumps'), os.uname().release)
        if result:
            print(json.dumps(result))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Wi-Fi coredump not archived: {error}\n')


if __name__ == '__main__':
    main()
