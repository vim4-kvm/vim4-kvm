#!/usr/bin/env python3
"""Inventory a matched build, then register its installed dual-kernel runtime.

inventory --image Image --modules STAGE/lib/modules/RELEASE --output build.json
register build.json [--source-label OneKvmTest]

Registration requires root on the board after installing the matching Image,
DTB and complete module set. It preserves the current default and data. It does
not install files, enable applications, reboot or promise automatic fallback.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def release(image):
    found = re.search(rb'Linux version ([^ ]+) ', image.read_bytes())
    if not found:
        raise ValueError('Image does not contain its kernel release')
    return found[1].decode('ascii')


def modules(root):
    return {str(path.relative_to(root)): path for path in root.rglob('*')
            if path.is_file() and not path.is_symlink()
            and path.name.endswith(('.ko', '.ko.xz', '.ko.zst'))}


def boot_profile(source, legacy_services=()):
    words = [word for word in source['APPEND'].split()
             if not word.startswith(('systemd.mask=', 'vim4.one_kvm='))]
    words += ['vim4.full_kvm=1'] + ['systemd.mask=' + unit for unit in (
        'tvserver.service', 'audioserver.service', 'one-kvm-edge.service',
        'one-kvm-edge-gateway.service', 'one-kvm-edge-usb.service', *legacy_services)]
    return {'LINUX': '/edge/Image', 'FDT': '/edge/vim4.dtb', 'APPEND': ' '.join(words)}


def update_boot_entry(text, existing, previous, full):
    if existing == full:
        return text
    if existing is None:
        return text + '\nLABEL FullKvm\n' + ''.join(f'  {key} {value}\n' for key, value in full.items())
    if existing != previous:
        raise ValueError('FullKvm has custom boot arguments; refusing to replace it')
    # Upgrade only our exact earlier profile, leaving every other label intact.
    label = None
    lines = []
    for line in text.splitlines(keepends=True):
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0].upper() == 'LABEL':
            label = fields[1].strip()
        if label == 'FullKvm' and fields and fields[0].upper() == 'APPEND':
            line = '  APPEND ' + full['APPEND'] + '\n'
        lines.append(line)
    return ''.join(lines)


def inventory(args):
    version = release(args.image)
    if version != args.modules.name or not version.startswith('7.'):
        raise ValueError('Image and staged modules must have the same 7.x release')
    files = modules(args.modules)
    if not files:
        raise ValueError('No staged kernel modules')
    data = {'release': version, 'image_sha256': digest(args.image),
            'module_sha256': {name: digest(path) for name, path in sorted(files.items())}}
    with args.output.open('x') as output:
        output.write(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'release': version, 'modules': len(files), 'image': data['image_sha256']}))


def register(args):
    if os.geteuid() != 0:
        raise ValueError('Registration requires root')
    sys.path.insert(0, '/usr/lib/vim4-kvm/python')
    import vim4boot as boot
    proof = json.loads(args.proof.read_text())
    version = proof['release']
    if version != '7.3.0-rc7-vim4kvm-uhd1+':
        raise ValueError('No validated application launcher for this kernel release')
    if digest(boot.BOOT / 'edge/Image') != proof['image_sha256']:
        raise ValueError('Installed mainline Image differs from the build inventory')
    root = Path('/lib/modules') / version
    current = modules(root)
    expected = proof['module_sha256']
    if not expected or current.keys() != expected.keys():
        raise ValueError('Installed module set differs from the complete build inventory')
    for name, path in current.items():
        if digest(path) != expected[name]:
            raise ValueError('Installed module differs from build: ' + name)
    original = boot.CONFIG.read_text()
    old_default = boot.default_label(original)
    entries = boot.boot_entries(original)
    source = entries[args.source_label]
    if source.get('LINUX') != '/edge/Image' or source.get('FDT') != '/edge/vim4.dtb':
        raise ValueError('Expected the previously qualified HDMI test boot entry')
    legacy = ['binder.service', 'bluetooth-khadas.service']
    rc = Path('/etc/rc.local')
    # This exact vendor script only generates host keys and writes old BSP
    # sysfs permissions. Preserve administrator scripts rather than masking them.
    if rc.is_file() and digest(rc) == 'a9e42abf50a4dd729df0459e9d8c18d6773fa3d17415f845bc5d21be3ebb5db8':
        if not Path('/etc/ssh/ssh_host_ed25519_key').is_file():
            raise ValueError('Generate SSH host keys before registering the mainline runtime')
        legacy.append('rc-local.service')
    full = boot_profile(source, legacy)
    text = update_boot_entry(original, entries.get('FullKvm'), boot_profile(source), full)
    entries = boot.boot_entries(text)
    vendor = release(boot.BOOT / entries['Default']['LINUX'].lstrip('/'))
    if not vendor.startswith('5.15.'):
        raise ValueError('Default must retain the installed 5.15 kernel')
    records = []
    for identifier, label, kernel in (('vendor', 'Default', vendor), ('mainline', 'FullKvm', version)):
        fields = entries[label]
        files = set()
        for key in ('LINUX', 'INITRD', 'FDT'):
            if key in fields:
                files.add(boot.BOOT / fields[key].lstrip('/'))
        if 'FDTDIR' in fields:
            files.update(path for path in (boot.BOOT / fields['FDTDIR'].lstrip('/')).rglob('*') if path.is_file())
        module_root = Path('/lib/modules') / kernel
        if not module_root.is_dir():
            raise ValueError('Kernel module directory is missing')
        files.update(path for path in module_root.rglob('*') if path.is_file() and not path.is_symlink())
        record = {'id': identifier, 'label': label, 'name': 'Linux ' + ('5.15' if identifier == 'vendor' else '7.x'),
                  'release': kernel, 'boot': fields, 'artifacts': {str(path): digest(path) for path in sorted(files)}}
        boot.validate_entry(record, text, hashes=True)
        records.append(record)
    backup = boot.CONFIG.with_name('extlinux.conf.before-full-runtime')
    if not backup.exists():
        boot.atomic_write(backup, original.encode())
    boot.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    try:
        if text != original:
            boot.atomic_write(boot.CONFIG, text.encode())
        boot.atomic_write(boot.MANIFEST, (json.dumps(records, indent=2) + '\n').encode())
    except Exception:
        if text != original:
            boot.atomic_write(boot.CONFIG, original.encode())
        raise
    assert boot.default_label(boot.CONFIG.read_text()) == old_default
    print(json.dumps({'default': old_default, 'registered': [
        {'id': record['id'], 'release': record['release'], 'artifacts': len(record['artifacts'])} for record in records]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('inventory')
    build.add_argument('--image', type=Path, required=True)
    build.add_argument('--modules', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    installed = commands.add_parser('register')
    installed.add_argument('proof', type=Path)
    installed.add_argument('--source-label', default='OneKvmTest')
    args = parser.parse_args()
    try:
        (inventory if args.command == 'inventory' else register)(args)
    except (ValueError, OSError, KeyError) as failure:
        parser.exit(1, str(failure) + '\n')


if __name__ == '__main__':
    main()
