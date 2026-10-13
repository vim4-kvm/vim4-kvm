#!/usr/bin/python3
"""Configure the VIM4 default boot for ordered ext4 writes; takes effect at boot."""
import argparse
import os
from pathlib import Path
import tempfile


def transform(fstab, extlinux):
    entries = []
    found_root = False
    for line in fstab.splitlines(keepends=True):
        fields = line.split()
        if fields and not line.lstrip().startswith('#') and len(fields) >= 6 and fields[1] in ('/', '/boot'):
            if fields[2] != 'ext4':
                raise ValueError('Expected ext4 for root and boot')
            found_root |= fields[1] == '/'
            options = [o for o in fields[3].split(',') if not o.startswith('commit=')]
            # Keep the journal mode out of fstab: the Stock boot entry may
            # deliberately select writeback, which cannot change on remount.
            if any(o.startswith('data=') for o in options):
                raise ValueError('Review explicit fstab journal mode before applying boot policy')
            fields[3] = ','.join(options + ['commit=5'])
            line = '\t'.join(fields) + '\n'
        entries.append(line)
    if not found_root:
        raise ValueError('No root filesystem entry')
    boot = []
    label = None
    changed = 0
    for line in extlinux.splitlines(keepends=True):
        fields = line.split()
        if fields and fields[0].upper() == 'LABEL':
            label = fields[1]
        if fields and fields[0].upper() == 'APPEND' and label == 'Default':
            for arg in fields[1:]:
                if arg.startswith('rootflags=') and arg not in ('rootflags=data=writeback', 'rootflags=data=ordered'):
                    raise ValueError('Review custom rootflags before applying boot policy')
            args = [arg for arg in fields[1:] if not arg.startswith('rootflags=')]
            # Linux uses the last rootflags value, after the vendor bootargs.
            line = '  APPEND ' + ' '.join(args + ['rootflags=data=ordered']) + '\n'
            changed += 1
        boot.append(line)
    if changed != 1:
        raise ValueError('Expected exactly one Default APPEND entry')
    return ''.join(entries), ''.join(boot)


def replace(path, content):
    if path.read_text() == content:
        return
    info = path.stat()
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            os.fchmod(output.fileno(), info.st_mode & 0o777)
            os.fchown(output.fileno(), info.st_uid, info.st_gid)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def configure(root):
    fstab, extlinux = root / 'etc/fstab', root / 'boot/extlinux/extlinux.conf'
    filesystem, boot = transform(fstab.read_text(), extlinux.read_text())
    replace(fstab, filesystem)
    replace(extlinux, boot)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Mounted Ubuntu root, or / on the board')
    parser.add_argument('--check', action='store_true', help='Read-only validation')
    args = parser.parse_args()
    if args.check:
        original = ((args.root / 'etc/fstab').read_text(), (args.root / 'boot/extlinux/extlinux.conf').read_text())
        if transform(*original) != original:
            raise SystemExit('Root filesystem boot policy is not configured')
        print('PASS: ordered root boot policy and 5-second commits')
    else:
        configure(args.root)
        print('Configured ext4 ordered data and 5-second commits; reboot to apply')
