#!/usr/bin/env python3
"""Inventory a matched build, then register its installed dual-kernel runtime.

inventory --image Image --modules STAGE/lib/modules/RELEASE --output build.json
register build.json [--framebuffer-console]

Registration requires root on the board after installing the matching Image,
DTB and complete module set. It preserves the current default and data. It does
not install files, enable applications, reboot or promise automatic fallback.
install stages a sealed complete package before atomically switching Mainline.
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

# Runs from a repository checkout; the board may still have an older installed vim4boot.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'board'))
from vim4boot import is_mainline_release

BOOT_FILES = ('Image', 'vim4.dtb', 'panfrost.dtb', 'config', 'Module.symvers', 'vmlinux.btf', 'manifest.json')


def check_space(boot_root, payload):
    required = sum((payload / name).stat().st_size + 4096 for name in BOOT_FILES)
    required += 16384  # Candidate directories and the atomic extlinux replacement.
    if shutil.disk_usage(boot_root).free < required:
        raise ValueError('Insufficient /boot space for the complete mainline runtime')
    return required


def atomic_copy(source, destination):
    """Keep the previous executable intact until its complete replacement is durable."""
    with tempfile.NamedTemporaryFile(prefix='.' + destination.name + '-',
                                     dir=destination.parent, delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        shutil.copyfile(source, staging)
        staging.chmod(source.stat().st_mode & 0o777)
        with staging.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(staging, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        staging.unlink(missing_ok=True)


def preflight_root_space(boot_root, module_bytes, runtime_files, firmware, boot_bytes):
    runtime_bytes = sum(p.stat().st_size + 4096 for p in runtime_files)
    required = module_bytes + runtime_bytes + firmware.stat().st_size + 16384
    if boot_root.stat().st_dev == Path('/').stat().st_dev:
        required += boot_bytes
    if shutil.disk_usage(Path('/')).free < required:
        raise ValueError('Insufficient root space for complete modules, runtime and firmware')


def mainline_append(append):
    """Keep firmware PD ownership while preserving other module blacklists."""
    tokens = append.split()
    blocked = [name for token in tokens if token.startswith('module_blacklist=')
               for name in token.split('=', 1)[1].split(',') if name]
    blocked = list(dict.fromkeys([*blocked, 'fusb302']))
    tokens = [token for token in tokens if not token.startswith('module_blacklist=')]
    return ' '.join(tokens + ['module_blacklist=' + ','.join(blocked)])


def upgrade_registration(boot, original, report, payload, kernel_dir):
    """Preserve other profiles and arguments while applying Mainline PD policy."""
    fields = boot.boot_entries(original.decode())['Mainline']
    prefix = '/' + str(kernel_dir.relative_to(boot.BOOT))
    full = dict(fields, LINUX=prefix + '/Image', FDT=prefix + '/vim4.dtb',
                APPEND=mainline_append(fields['APPEND']))
    label, lines = None, []
    for line in original.decode().splitlines(keepends=True):
        words = line.split(None, 1)
        if len(words) == 2 and words[0].upper() == 'LABEL':
            label = words[1].strip()
        if label == 'Mainline' and words and words[0].upper() in ('LINUX', 'FDT', 'APPEND'):
            line = '  ' + words[0].upper() + ' ' + full[words[0].upper()] + '\n'
        lines.append(line)
    text = ''.join(lines)
    records = json.loads(boot.MANIFEST.read_text())
    current = next(record for record in records if record['label'] == 'Mainline')
    if current['release'] != release(boot.BOOT/fields['LINUX'].lstrip('/')) or current['boot'] != fields:
        raise ValueError('Installed Mainline registry differs from the running boot profile')
    artifacts = {str(kernel_dir / name): digest(payload / name) for name in ('Image', 'vim4.dtb')}
    artifacts.update({str(Path('/lib/modules') / report['release'] / name): value
                      for name, value in report['modules'].items()})
    current.update(release=report['release'], boot=full, artifacts=artifacts)
    return text, records


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


def boot_profile(source, legacy_services=(), *, version, framebuffer_console=False):
    words = [word for word in source['APPEND'].split()
             if not word.startswith(('systemd.mask=', 'vim4.one_kvm=', 'vim4.full_kvm=', 'vim4.eth_mac='))]
    words += ['vim4.full_kvm=1', 'vim4.eth_mac=${eth_mac}'] + ['systemd.mask=' + unit for unit in (
        'tvserver.service', 'audioserver.service', 'one-kvm-edge.service',
        'one-kvm-edge-gateway.service', 'one-kvm-edge-usb.service', *legacy_services)]
    if framebuffer_console and 'console=tty0' not in words:
        # Serial remains the last console and therefore /dev/console's target.
        words.insert(0, 'console=tty0')
    prefix = '/kernels/' + version
    return {'LINUX': prefix+'/Image', 'FDT': prefix+'/vim4.dtb',
            'APPEND': mainline_append(' '.join(words))}


def update_boot_entry(text, existing, previous, full):
    if existing == full:
        return text
    # Upgrade the earlier exact profile without factory-MAC handoff. Other
    # administrator changes still require an explicit deployment review.
    # Recognize only our exact earlier profiles: before the factory-MAC
    # handoff and before the adopted firmware-PD policy. Other arguments stay
    # subject to the existing administrator-change refusal.
    before_pd = []
    for word in full['APPEND'].split():
        if word.startswith('module_blacklist='):
            names = [name for name in word.split('=', 1)[1].split(',') if name != 'fusb302']
            if names:
                before_pd.append('module_blacklist=' + ','.join(names))
        else:
            before_pd.append(word)
    compatible = [previous]
    for words in (full['APPEND'].split(), before_pd):
        compatible += [{**full, 'APPEND': ' '.join(words)},
                       {**full, 'APPEND': ' '.join(w for w in words
                                                 if w != 'vim4.eth_mac=${eth_mac}')}]
    if existing not in compatible:
        raise ValueError('Mainline has custom boot arguments; refusing to replace it')
    # Upgrade only our exact earlier profile, leaving every other label intact.
    label = None
    lines = []
    for line in text.splitlines(keepends=True):
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0].upper() == 'LABEL':
            label = fields[1].strip()
        if label == 'Mainline' and fields and fields[0].upper() == 'APPEND':
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
    import vim4boot as boot
    proof = json.loads(args.proof.read_text())
    version = proof['release']
    if not is_mainline_release(version):
        raise ValueError('No validated application launcher for this kernel release')
    prefix = '/kernels/' + version
    if digest(boot.BOOT / prefix.lstrip('/') / 'Image') != proof['image_sha256']:
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
    source = entries['Mainline']
    if source.get('LINUX') != prefix+'/Image' or source.get('FDT') != prefix+'/vim4.dtb':
        raise ValueError('Expected Mainline to use the matched release directory')
    legacy = ['binder.service', 'bluetooth-khadas.service']
    rc = Path('/etc/rc.local')
    # This exact vendor script only generates host keys and writes old BSP
    # sysfs permissions. Preserve administrator scripts rather than masking them.
    if rc.is_file() and digest(rc) == 'a9e42abf50a4dd729df0459e9d8c18d6773fa3d17415f845bc5d21be3ebb5db8':
        if not Path('/etc/ssh/ssh_host_ed25519_key').is_file():
            raise ValueError('Generate SSH host keys before registering the mainline runtime')
        legacy.append('rc-local.service')
    previous = boot_profile(source, version=version)
    framebuffer_console = getattr(args, 'framebuffer_console', False)
    if framebuffer_console and source == boot_profile(source, legacy, version=version):
        previous = boot_profile(source, legacy, version=version)
    full = boot_profile(source, legacy, version=version, framebuffer_console=framebuffer_console)
    text = update_boot_entry(original, source, previous, full)
    entries = boot.boot_entries(text)
    vendor = release(boot.BOOT / entries['Vendor']['LINUX'].lstrip('/'))
    if not vendor.startswith('5.15.'):
        raise ValueError('Vendor must retain the installed 5.15 kernel')
    records = []
    for identifier, label, kernel in (('vendor', 'Vendor', vendor), ('mainline', 'Mainline', version)):
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
        record = {'id': identifier, 'label': label, 'name': '厂商内核' if identifier == 'vendor' else '主线内核',
                  'release': kernel, 'boot': fields, 'artifacts': {str(path): digest(path) for path in sorted(files)}}
        boot.validate_entry(record, text, hashes=True)
        records.append(record)
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
    """Stage a complete release, then atomically switch Mainline; preserve the default."""
    if os.geteuid() != 0:
        raise ValueError('Installation requires root')
    import vim4boot as boot
    original = boot.CONFIG.read_bytes()
    entries = boot.boot_entries(original.decode())
    label = boot.default_label(original.decode())
    previous = release(boot.BOOT / entries['Mainline']['LINUX'].lstrip('/'))
    prefix = '/kernels/' + previous
    if entries['Mainline'].get('LINUX') != prefix+'/Image' or entries['Mainline'].get('FDT') != prefix+'/vim4.dtb':
        raise ValueError('Mainline must use its installed release directory')
    if not Path('/lib').is_symlink():
        raise ValueError('Expected Ubuntu /lib symlink')
    with tempfile.TemporaryDirectory(prefix='vim4-kernel-install-') as temporary:
        root = Path(temporary)
        with tarfile.open(args.archive) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
                    raise ValueError('Unsafe package member: ' + member.name)
            archive.extractall(root, filter='data')
        candidate = json.loads((root/'candidate.json').read_text())
        actual_files = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        if actual_files - {'candidate.json'} != set(candidate['sha256']):
            raise ValueError('Package file inventory differs from candidate.sha256')
        for name, expected in candidate['sha256'].items():
            if digest(root/name) != expected:
                raise ValueError('Package hash mismatch: ' + name)
        report = json.loads((root/'manifest.json').read_text())
        version = report['release']
        if not is_mainline_release(version) or release(root/'Image') != version:
            raise ValueError('Unexpected unified kernel Image')
        with tarfile.open(root/'modules.tar.gz') as archive:
            actual = {}
            module_bytes = 0
            for member in archive:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != version:
                    raise ValueError('Unsafe module member: ' + member.name)
                if member.isdir():
                    module_bytes += 4096
                    continue
                if not member.isfile():
                    raise ValueError('Nonregular module member: ' + member.name)
                name = str(Path(*path.parts[1:]))
                if name in actual:
                    raise ValueError('Duplicate module member: ' + name)
                actual[name] = hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest()
                module_bytes += member.size + 4096
            if actual != report['modules']:
                raise ValueError('Incomplete or mismatched module archive')
        kernel_dir = boot.BOOT/'kernels'/version
        if kernel_dir.exists():
            raise ValueError('Use a new candidate boot directory; previous staging is retained')
        boot_bytes = check_space(boot.BOOT, root)
        runtime_files = sorted(p for p in (root/'runtime/usr').rglob('*') if p.is_file())
        updates = Path('/lib/firmware/updates')
        firmware_name = Path('brcm/brcmfmac43752-sdio.khadas,vim4.bin')
        firmware = updates/previous/firmware_name
        if digest(firmware) != '3ff292ab216c13ce3019f6b4cc4234a15a81c8b553014b122f748efd9465676d':
            raise ValueError('Expected the qualified BCM43752 .217 firmware')
        text, records = upgrade_registration(boot, original, report, root, kernel_dir)
        registration = (json.dumps(records, indent=2)+'\n').encode()
        preflight_root_space(boot.BOOT, module_bytes, runtime_files, firmware, boot_bytes)
        destination = updates/version/firmware_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(firmware, destination)
        if digest(destination) != digest(firmware):
            raise ValueError('Installed BCM43752 firmware hash mismatch')
        install_complete_modules(root/'modules.tar.gz', Path('/lib/modules')/version, report['modules'])
        kernel_dir.mkdir(parents=True)
        for name in BOOT_FILES:
            shutil.copyfile(root/name, kernel_dir/name)
            if digest(kernel_dir/name) != candidate['sha256'][name]:
                raise ValueError('Staged boot file hash mismatch: ' + name)
        for source in runtime_files:
            destination = Path('/usr')/source.relative_to(root/'runtime/usr')
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.chmod(0o755)
            atomic_copy(source, destination)
            if digest(destination) != candidate['sha256'][str(source.relative_to(root))]:
                raise ValueError('Installed runtime hash mismatch: ' + str(destination))
        for record in records:
            boot.validate_entry(record, text, hashes=True)
        os.sync()
        boot.atomic_write(boot.MANIFEST, registration)
        os.sync()
        boot.atomic_write(boot.CONFIG, text.encode())
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
    package = commands.add_parser('install')
    package.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        {'inventory': inventory, 'register': register, 'install': install}[args.command](args)
    except (ValueError, OSError, KeyError) as failure:
        parser.exit(1, str(failure) + '\n')


if __name__ == '__main__':
    main()
