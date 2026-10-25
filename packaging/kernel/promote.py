#!/usr/bin/env python3
"""Promote a boot-tested vendor staging tree, preserving verified rollback files.

Run with both board locks held. This registers a prepared, already running
candidate; it does not unpack archives, rebuild initrds or reboot the board.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def replacement(text, label, fields, rollback_label, boot):
    entries = boot.boot_entries(text)
    if rollback_label in entries or label not in entries:
        raise ValueError('Missing current entry or rollback label already exists')
    lines = []
    current = None
    for line in text.splitlines(keepends=True):
        words = line.strip().split(None, 1)
        if len(words) == 2 and words[0].upper() == 'LABEL':
            current = words[1]
        if current == label and len(words) == 2 and words[0].upper() in fields:
            line = f'  {words[0].upper()} {fields[words[0].upper()]}\n'
        lines.append(line)
    updated = ''.join(lines) + f'\nLABEL {rollback_label}\n' + ''.join(
        f'  {key} {value}\n' for key, value in entries[label].items())
    after = boot.boot_entries(updated)
    if after[label] != fields or after[rollback_label] != entries[label]:
        raise ValueError('Boot profile could not be replaced safely')
    if any(after[name] != value for name, value in entries.items() if name != label):
        raise ValueError('Another boot profile changed')
    return updated


def compress_image(path, backup):
    saved = backup / ('image-' + path.name)
    if saved.exists() or (backup / (saved.name + '.gz')).exists():
        raise FileExistsError('Image backup already exists')
    if path.is_symlink() or not path.is_file():
        raise ValueError('Compression requires a regular Image')
    shutil.copy2(path, saved)
    with saved.open('rb') as source, (backup / (saved.name + '.gz')).open('xb') as output:
        with gzip.GzipFile(filename='', mode='wb', compresslevel=9, fileobj=output, mtime=0) as zipped:
            shutil.copyfileobj(source, zipped)
    compressed = backup / (saved.name + '.gz')
    if gzip.decompress(compressed.read_bytes()) != path.read_bytes():
        raise ValueError('Compressed Image does not match original bytes')
    subprocess.run(['sync'], check=True)
    with compressed.open('rb') as source, path.open('wb') as output:
        shutil.copyfileobj(source, output)
        output.flush()
        os.fsync(output.fileno())
    if digest(path) != digest(compressed):
        raise ValueError('Installed compressed Image failed verification')
    return digest(path)


def promote(args, boot):
    version = args.release
    if not re.fullmatch(r'5\.15\.[A-Za-z0-9.+_-]+', version):
        raise ValueError('A vendor 5.15 release is required')
    if subprocess.check_output(['uname', '-r'], text=True).strip() != version:
        raise ValueError('Only the currently boot-tested kernel may be promoted')
    source = args.candidate
    raw = source / f'boot/vmlinuz-{version}'
    if gzip.decompress((source / 'Image.gz').read_bytes()) != raw.read_bytes():
        raise ValueError('Candidate compressed Image differs from staged Image')
    if f'Linux version {version} '.encode() not in raw.read_bytes():
        raise ValueError('Candidate Image release does not match')
    staged = source / 'lib/modules' / version
    installed = Path('/lib/modules') / version
    expected = {str(path.relative_to(staged)): digest(path) for path in staged.rglob('*.ko')}
    actual = {str(path.relative_to(installed)): digest(path) for path in installed.rglob('*.ko')}
    if not expected or expected != actual:
        raise ValueError('Complete installed modules differ from candidate')
    text = boot.CONFIG.read_text()
    records = boot.installed()
    for record in records:
        boot.validate_entry(record, text, hashes=True)
    vendor = next(record for record in records if record['id'] == 'vendor')
    if boot.default_label(text) != vendor['label']:
        raise ValueError('Current default is not the vendor baseline')
    image = boot.BOOT / ('vmlinuz-' + version)
    initrd = boot.BOOT / ('initrd.img-' + version)
    dtb = boot.BOOT / ('dtb-' + version)
    if any(path.exists() for path in (image, initrd, dtb)):
        raise ValueError('Candidate boot files already exist')
    args.backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(boot.CONFIG, args.backup / 'extlinux.conf')
    shutil.copy2(boot.MANIFEST, args.backup / 'kernels-before.json')
    for path in args.compress_image:
        if not path.is_relative_to(boot.BOOT) or '..' in path.parts:
            raise ValueError('Compression target must be inside /boot')
        checksum = compress_image(path, args.backup)
        for record in records:
            if str(path) in record['artifacts']:
                record['artifacts'][str(path)] = checksum
    rollback_records = copy.deepcopy(records)
    boot.atomic_write(args.backup / 'rollback-kernels.json',
                      (json.dumps(rollback_records, indent=2) + '\n').encode())
    boot.atomic_write(boot.MANIFEST, (json.dumps(records, indent=2) + '\n').encode())
    required = sum((source / name).stat().st_size for name in ('Image.gz', 'initrd.img'))
    if shutil.disk_usage(boot.BOOT).free < required + 2 * 1024 * 1024:
        raise ValueError('Not enough boot space; baseline entries remain unchanged')
    shutil.copyfile(source / 'Image.gz', image)
    shutil.copyfile(source / 'initrd.img', initrd)
    old_dtb = boot.BOOT / vendor['boot']['FDTDIR'].lstrip('/')
    shutil.copytree(old_dtb, dtb, symlinks=True)
    for name in ('kvim4', 'kvim4n'):
        shutil.copyfile(source / f'boot/dtb-{version}/amlogic/{name}.dtb', dtb / f'amlogic/{name}.dtb')
    shutil.copyfile(source / f'boot/config-{version}', boot.BOOT / ('config-' + version))
    (boot.BOOT / ('System.map-' + version)).symlink_to(source / f'boot/System.map-{version}')
    fields = {**vendor['boot'], 'LINUX': '/' + image.name, 'INITRD': '/' + initrd.name,
              'FDTDIR': '/' + dtb.name}
    updated = replacement(text, vendor['label'], fields, args.rollback_label, boot)
    files = {image, initrd}
    files.update(path for path in dtb.rglob('*') if path.is_file())
    files.update(path for path in installed.rglob('*') if path.is_file() and not path.is_symlink())
    vendor.update(release=version, boot=fields, artifacts={str(path): digest(path) for path in sorted(files)})
    for record in records:
        boot.validate_entry(record, updated, hashes=True)
    subprocess.run(['sync'], check=True)
    boot.atomic_write(boot.MANIFEST, (json.dumps(records, indent=2) + '\n').encode())
    boot.atomic_write(boot.CONFIG, updated.encode())
    print(json.dumps(boot.status(), ensure_ascii=False))


def rollback(args, boot):
    text = (args.backup / 'extlinux.conf').read_text()
    records = json.loads((args.backup / 'rollback-kernels.json').read_text())
    for record in records:
        boot.validate_entry(record, text, hashes=True)
    if args.check:
        print('Rollback Image, initrd, DTBs, complete modules and boot profiles verified')
        return
    boot.atomic_write(boot.MANIFEST, (json.dumps(records, indent=2) + '\n').encode())
    boot.atomic_write(boot.CONFIG, text.encode())
    subprocess.run(['sync'], check=True)
    print('Previous default restored; reboot explicitly when ready')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    install = commands.add_parser('promote')
    install.add_argument('--candidate', type=Path, required=True)
    install.add_argument('--release', required=True)
    install.add_argument('--rollback-label', required=True)
    install.add_argument('--compress-image', type=Path, action='append', default=[])
    install.add_argument('--backup', type=Path, required=True)
    restore = commands.add_parser('rollback')
    restore.add_argument('--backup', type=Path, required=True)
    restore.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root with both board locks held')
    sys.path.insert(0, '/usr/lib/vim4-kvm/python')
    import vim4boot as boot
    if args.action == 'promote':
        if not re.fullmatch(r'[A-Za-z0-9_-]+', args.rollback_label):
            parser.error('Invalid rollback label')
        promote(args, boot)
    else:
        rollback(args, boot)


if __name__ == '__main__':
    main()
