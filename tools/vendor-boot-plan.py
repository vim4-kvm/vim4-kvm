#!/usr/bin/env python3
"""Generate a one-shot 5.15 extlinux file from an OFFLINE boot snapshot.

No SSH, staging, reboot or persistent boot changes. The output must be reviewed
against a fresh board inventory before a reserved serial-console window.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def parse_config(text):
    default, entries, current = None, {}, None
    for line in text.splitlines():
        fields = line.strip().split(None, 1)
        if not fields or fields[0].startswith('#'):
            continue
        key = fields[0].upper()
        value = fields[1] if len(fields) == 2 else ''
        if key == 'DEFAULT':
            if default is not None:
                raise ValueError('duplicate DEFAULT')
            default = value
        elif key == 'LABEL':
            if value in entries:
                raise ValueError('duplicate LABEL')
            current = entries[value] = {}
        elif key in ('LINUX', 'KERNEL', 'INITRD', 'FDT', 'APPEND') and current is not None:
            key = 'LINUX' if key == 'KERNEL' else key
            if key in current:
                raise ValueError('duplicate boot field')
            current[key] = value
    return default, entries


def generate(text, label, resolved_profile=None):
    default, entries = parse_config(text)
    if default not in entries or entries[default].get('LINUX') != '/edge/Image':
        raise ValueError('default must still be the 7.3 /edge/Image entry')
    if label == default or label not in entries:
        raise ValueError('select a separate vendor label')
    entry = resolved_profile if resolved_profile is not None else entries[label]
    for key in ('LINUX', 'INITRD', 'FDT'):
        value = entry.get(key, '')
        path = PurePosixPath(value)
        if not re.fullmatch(r'/[A-Za-z0-9_./+-]+', value) or '..' in path.parts:
            raise ValueError('unsafe or missing vendor ' + key)
        if '5.15.137-vim4kvm' not in value:
            raise ValueError('vendor artifact must name 5.15.137-vim4kvm: ' + key)
    append = entry.get('APPEND', '')
    if not append or re.search(r'[\x00-\x1f$;`\\]', append):
        raise ValueError('unsafe or missing vendor APPEND')
    tokens = append.split()
    if not any(token.startswith('root=') for token in tokens):
        raise ValueError('vendor root argument required')
    if any(token.startswith(('init=', 'rdinit=', 'systemd.unit=')) for token in tokens):
        raise ValueError('unexpected init override')
    # Preserve vendor-specific root/console/CMA/PD arguments, not edge arguments.
    tokens = [token for token in tokens if not token.startswith(('panic=', 'oops='))]
    tokens += ['oops=panic', 'panic=20']
    config = 'DEFAULT vendor-once\nTIMEOUT 1\nLABEL vendor-once\n'
    for key in ('LINUX', 'INITRD', 'FDT'):
        config += f'  {key} {entry[key]}\n'
    config += '  APPEND ' + ' '.join(tokens) + '\n'
    digest = hashlib.sha256(text.encode()).hexdigest()
    destination = f'/perf-vendor-{digest[:16]}.conf'
    return dict(config=config, source_sha256=digest, resolved_vendor_profile=entry,
                boot_partition='mmc 1:1',
                destination_on_boot=destination,
                serial_command=f'sysboot mmc 1:1 any ${{pxefile_addr_r}} {destination}; reset',
                status='offline plan; watchdog and artifact/module checks still required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extlinux', type=Path, required=True, help='local snapshot, not a board path')
    parser.add_argument('--vendor-label', required=True)
    parser.add_argument('--vendor-profile', type=Path,
                        help='reviewed JSON with resolved LINUX/INITRD/FDT/APPEND')
    parser.add_argument('--output', type=Path, required=True, help='new local directory')
    args = parser.parse_args()
    profile = json.loads(args.vendor_profile.read_text()) if args.vendor_profile else None
    result = generate(args.extlinux.read_text(), args.vendor_label, profile)
    args.output.mkdir()
    (args.output / 'extlinux.conf').write_text(result['config'])
    (args.output / 'plan.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
