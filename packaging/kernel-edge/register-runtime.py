#!/usr/bin/env python3
"""Inventory a matched build, then register its installed dual-kernel runtime.

inventory --image Image --modules STAGE/lib/modules/RELEASE --output build.json
register build.json [--source-label OneKvmTest] [--framebuffer-console]

Registration requires root on the board after installing the matching Image,
DTB and complete module set. It preserves the current default and data. It does
not install files, enable applications, reboot or promise automatic fallback.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def release(image):
    data = image.read_bytes()
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    found = re.search(rb'Linux version ([^ ]+) ', data)
    if not found:
        raise ValueError('Image does not contain its kernel release')
    return found[1].decode('ascii')


def modules(root):
    return {str(path.relative_to(root)): path for path in root.rglob('*')
            if path.is_file() and not path.is_symlink()
            and path.name.endswith(('.ko', '.ko.xz', '.ko.zst'))}


def boot_profile(source, legacy_services=(), *, framebuffer_console=False):
    words = [word for word in source['APPEND'].split()
             if not word.startswith(('systemd.mask=', 'vim4.one_kvm='))]
    words += ['vim4.full_kvm=1', 'vim4.eth_mac=${eth_mac}'] + ['systemd.mask=' + unit for unit in (
        'tvserver.service', 'audioserver.service', 'one-kvm-edge.service',
        'one-kvm-edge-gateway.service', 'one-kvm-edge-usb.service', *legacy_services)]
    if framebuffer_console and 'console=tty0' not in words:
        # Serial remains the last console and therefore /dev/console's target.
        words.insert(0, 'console=tty0')
    return {'LINUX': '/edge/Image', 'FDT': '/edge/vim4.dtb', 'APPEND': ' '.join(words)}


def update_boot_entry(text, existing, previous, full):
    if existing == full:
        return text
    if existing is None:
        return text + '\nLABEL FullKvm\n' + ''.join(f'  {key} {value}\n' for key, value in full.items())
    # Upgrade the earlier exact profile without factory-MAC handoff. Other
    # administrator changes still require an explicit deployment review.
    before_mac = {**full, 'APPEND':' '.join(w for w in full['APPEND'].split()
                                          if w != 'vim4.eth_mac=${eth_mac}')}
    if existing != previous and existing != before_mac:
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
    if version not in ('7.3.0-rc7-vim4kvm-uhd1+', '7.3.0-vim4kvm-uhd1+', '7.3.0-vim4kvm-uhd6+', '7.3.0-vim4kvm-uhd7+'):
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
    previous = boot_profile(source)
    framebuffer_console = getattr(args, 'framebuffer_console', False)
    if framebuffer_console and entries.get('FullKvm') == boot_profile(source, legacy):
        previous = boot_profile(source, legacy)
    full = boot_profile(source, legacy, framebuffer_console=framebuffer_console)
    text = update_boot_entry(original, entries.get('FullKvm'), previous, full)
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
    if not getattr(args, 'no_backup', False) and not backup.exists():
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


def install_complete_modules(archive, root, expected):
    """Resume after a boot-file copy failure only with the exact complete set."""
    if root.exists() and any(root.iterdir()):
        paths = list(root.rglob('*'))
        if any(path.is_symlink() for path in paths):
            raise ValueError('Refusing to overwrite an existing module set')
        current = {str(path.relative_to(root)): digest(path) for path in paths if path.is_file()}
        if current != expected:
            raise ValueError('Refusing to overwrite an existing module set')
        return
    subprocess.run(['tar', 'xzf', str(archive), '-C', str(root.parent),
                    '--no-same-owner', '--keep-directory-symlink'], check=True)


def install(args):
    """Install the sealed kernel and matching modules, preserving the saved default."""
    if os.geteuid() != 0:
        raise ValueError('Installation requires root')
    sys.path.insert(0, '/usr/lib/vim4-kvm/python')
    import vim4boot as boot
    original = boot.CONFIG.read_bytes()
    entries = boot.boot_entries(original.decode())
    label = boot.default_label(original.decode())
    saved = release(boot.BOOT / entries[label]['LINUX'].lstrip('/'))
    if not Path('/lib').is_symlink():
        raise ValueError('Expected Ubuntu /lib symlink')
    with tempfile.TemporaryDirectory(prefix='vim4-edge-install-') as temporary:
        root = Path(temporary)
        with tarfile.open(args.archive) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
                    raise ValueError('Unsafe package member: ' + member.name)
            archive.extractall(root, filter='data')
        candidate = json.loads((root / 'candidate.json').read_text())
        for name, expected in candidate['sha256'].items():
            if digest(root / name) != expected:
                raise ValueError('Package hash mismatch: ' + name)
        report = json.loads((root / 'manifest.json').read_text())
        version = report['release']
        upgrade = version == '7.3.0-vim4kvm-uhd7+'
        if version not in ('7.3.0-vim4kvm-uhd6+', '7.3.0-vim4kvm-uhd7+') or release(root / 'Image') != version:
            raise ValueError('Unexpected unified kernel Image')
        if upgrade:
            if (label != 'FullKvm' or saved != '7.3.0-vim4kvm-uhd6+' or
                    entries[label].get('LINUX') != '/edge/Image' or entries[label].get('FDT') != '/edge/vim4.dtb'):
                raise ValueError('The uhd7 upgrade requires the installed uhd6 FullKvm kbase profile')
        elif not saved.startswith('5.15.'):
            raise ValueError('Installation requires 5.15 as the saved default')
        with tarfile.open(root / 'modules.tar.gz') as archive:
            actual = {}
            for member in archive:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != version:
                    raise ValueError('Unsafe module member: ' + member.name)
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError('Nonregular module member: ' + member.name)
                name = str(Path(*path.parts[1:]))
                if name in actual:
                    raise ValueError('Duplicate module member: ' + name)
                actual[name] = hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest()
            if actual != report['modules']:
                raise ValueError('Incomplete or mismatched module archive')
        edge = boot.BOOT / 'edge'
        edge.mkdir(exist_ok=True)
        boot_files = ('Image', 'vim4.dtb', 'panfrost.dtb', 'config', 'Module.symvers', 'vmlinux.btf', 'manifest.json')
        required = sum(max(0, (root / name).stat().st_size -
                           ((edge / name).stat().st_size if (edge / name).exists() else 0))
                       + 4096 for name in boot_files)
        if shutil.disk_usage(edge).free < required:
            raise ValueError('Insufficient /boot space for the complete edge runtime')
        if upgrade:
            updates = Path('/lib/firmware/updates')
            name = Path('brcm/brcmfmac43752-sdio.khadas,vim4.bin')
            firmware = updates / saved / name
            if digest(firmware) != '3ff292ab216c13ce3019f6b4cc4234a15a81c8b553014b122f748efd9465676d':
                raise ValueError('Expected the qualified BCM43752 .217 firmware')
            destination = updates / version / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(firmware, destination)
        install_complete_modules(root / 'modules.tar.gz', Path('/lib/modules') / version,
                                 report['modules'])
        for name in boot_files:
            shutil.copyfile(root / name, edge / name)
        for path in (root / 'runtime/usr').rglob('*'):
            if path.is_file():
                destination = Path('/usr') / path.relative_to(root / 'runtime/usr')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                destination.chmod(0o755)
        if not upgrade:
            binary = Path('/opt/vim4-onekvm-edge/one-kvm')
            binary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / 'runtime/one-kvm', binary)
            binary.chmod(0o755)
            for path in (root / 'runtime/gstreamer-1.0').iterdir():
                shutil.copyfile(path, Path('/usr/lib/vim4-kvm/mainline-gstreamer-1.0') / path.name)
        register(argparse.Namespace(proof=root / 'runtime-proof.json', source_label=args.source_label,
                                    framebuffer_console=True, no_backup=True))
    if boot.CONFIG.read_bytes() != original:
        raise ValueError('Boot configuration changed during installation')
    os.sync()
    print(f'Installed {version}; saved default remains {label}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('inventory')
    build.add_argument('--image', type=Path, required=True)
    build.add_argument('--modules', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    installed = commands.add_parser('register')
    installed.add_argument('--framebuffer-console', action='store_true',
                           help='Register tty0 output for a qualified simpledrm handoff')
    installed.add_argument('proof', type=Path)
    installed.add_argument('--source-label', default='OneKvmTest')
    installed.add_argument('--no-backup', action='store_true')
    package = commands.add_parser('install')
    package.add_argument('archive', type=Path)
    package.add_argument('--source-label', default='OneKvmTest')
    args = parser.parse_args()
    try:
        {'inventory': inventory, 'register': register, 'install': install}[args.command](args)
    except (ValueError, OSError, KeyError) as failure:
        parser.exit(1, str(failure) + '\n')


if __name__ == '__main__':
    main()
