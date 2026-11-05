#!/usr/bin/env python3
"""Prepare or locally stage a RAM-selected T7 trial. Never edits default boot files.

Staging changes board state: invoke only while holding board/heavy locks. This
tool does not reboot, use SSH, write U-Boot environment, or select the candidate.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import tomllib

SOURCES = Path(__file__).with_name('sources.toml')
RELEASE = '7.3.0-vim4kvm-uhd1+'
ROOT = Path('/var/lib/vim4-kvm/display-m1')
MODULE_ROOT = Path('/lib/modules')


def formal_baseline():
    return tomllib.loads(SOURCES.read_text())['retained_runtime']


def supported_baseline(release):
    return release.startswith('5.15.') or release == formal_baseline()['release']


def persistent_baseline_files(files):
    """RAM bind targets are verified in full after reboot removes the mounts."""
    return {name: value for name, value in files.items() if not name.startswith(('/usr/', '/opt/'))}


def validate_distinct_dt(properties, baseline_properties):
    if not properties or not all(name in baseline_properties for name in properties):
        raise ValueError('DT identity properties must first be captured on the baseline')
    for name, value in properties.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not re.fullmatch(r'(?:[0-9a-f]{2})*', value):
            raise ValueError('invalid DT identity property: ' + name)
    if not any(value != baseline_properties[name] for name, value in properties.items()):
        raise ValueError('DT identity must differ from the baseline in at least one property')


def candidate_parent(plan, metadata='manifest.json'):
    """Keep payload identity separate from the real kernel GNU build ID."""
    if 'namespace' not in plan and 'payload_id' not in plan:
        return ROOT if metadata == 'trial.json' else ROOT.parent / 'hdr2-unified'
    for key in ('namespace', 'payload_id'):
        value = plan.get(key, '')
        if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value):
            raise ValueError('invalid candidate ' + key)
    return ROOT.parent / 'ram-candidates' / plan['namespace'] / plan['payload_id']


def candidate_prefix(plan, metadata='manifest.json'):
    if not re.fullmatch('[0-9a-f]{40}', plan['build_id']):
        raise ValueError('invalid kernel build ID')
    return candidate_parent(plan, metadata) / plan['build_id']


def validate_release(release):
    if not re.fullmatch(r'7\.3\.[01]-vim4kvm-[A-Za-z0-9][A-Za-z0-9._-]*\+|\d+\.\d+(?:\.\d+)?-vim4-\d{8}(?:\.(?:[2-9]|[1-9]\d+))?', release):
        raise ValueError('invalid candidate release')


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def static_arm64(path):
    """The pre-systemd entry must run without the candidate's dynamic loader."""
    data = Path(path).read_bytes()
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('init must be little-endian ELF64')
    kind, machine = struct.unpack_from('<HH', data, 16)
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if kind != 2 or machine != 183 or size != 56 or not count:
        raise ValueError('init must be a static AArch64 executable')
    if offset + size * count > len(data):
        raise ValueError('truncated init program headers')
    kinds = [struct.unpack_from('<I', data, offset + i * size)[0] for i in range(count)]
    if 1 not in kinds or any(k in (2, 3) for k in kinds):
        raise ValueError('init needs a load segment and no dynamic loader')


def safe_member(member):
    name = PurePosixPath(member.name)
    if name.is_absolute() or '..' in name.parts or not name.parts:
        raise ValueError('unsafe archive path: ' + member.name)
    if not (member.isfile() or member.isdir()):
        raise ValueError('archive links/devices are forbidden: ' + member.name)
    return name


def validate_partuuid(partuuid):
    if not re.fullmatch(r'(?:[0-9a-f]{8}-[0-9a-f]{2}|'
                        r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})', partuuid):
        raise ValueError('filesystem UUID root requires baseline root_partuuid proof')


def trial_cmdline(state):
    """Boot without an initramfs while retaining the original stage proof."""
    tokens = state['cmdline'].strip().split()
    if any(token.startswith('root=UUID=') for token in tokens):
        partuuid = state.get('root_partuuid', '')
        validate_partuuid(partuuid)
        # Mainline resolves PARTUUID in-kernel; filesystem UUID needs userspace.
        tokens = [('root=PARTUUID=' + partuuid) if token.startswith('root=UUID=')
                  else token for token in tokens]
        if 'rootwait' not in tokens:
            tokens.append('rootwait')
    return ' '.join(tokens)


def trial_boot_command(prefix, file_size, header):
    """Keep large debug Images outside the T7 bootloader's low-memory hole."""
    command = f'sysboot mmc 1:2 any ${{pxefile_addr_r}} {prefix}/extlinux.conf; reset'
    arm64 = len(header) >= 64 and header[56:60] == b'ARM\x64'
    offset, image_size, flags = struct.unpack_from('<QQQ', header, 8) if arm64 else (0, 0, 0)
    # kvim4.c maps [0, 0x05100000) and [0x09000000, ...). The stock
    # kernel_addr_r is 0x01080000; booti rounds its base up to 2 MiB.
    relocated = ((0x01080000 - offset + 0x1fffff) & ~0x1fffff) + offset
    if max(0x01080000 + file_size, relocated + image_size) <= 0x05100000:
        return command
    # ARM64 flag bit 3 permits placement away from the base of RAM. These
    # candidates have no initramfs; FDT/PXE remain in their stock low regions.
    if not arm64 or not flags & 8 or not 0 <= offset < 0x200000 or image_size < file_size:
        raise ValueError('Large trial Image requires a relocatable ARM64 header')
    address = 0x20000000 + offset
    if address + image_size > 0x80000000:
        raise ValueError('Large trial Image exceeds the reviewed T7 load region')
    return f'setenv kernel_addr_r 0x{address:08x}; ' + command


def prepare(payload, init, baseline, output, release=RELEASE,
            baseline_release=None, baseline_id=None, namespace=None, payload_id=None):
    state = json.loads(baseline.read_text())
    baseline_release = state['release'] if baseline_release is None else baseline_release
    baseline_id = state['build_id'] if baseline_id is None else baseline_id
    if not supported_baseline(baseline_release):
        raise ValueError('prepare requires a 5.15 or formal baseline proof')
    validate_release(release)
    if not re.fullmatch(r'[0-9a-f]{40}', baseline_id):
        raise ValueError('baseline build ID must be explicit and complete')
    report = json.loads((payload / 'manifest.json').read_text())
    build_id = report['kernel_build_id']
    same_image = build_id == baseline_id
    if not re.fullmatch('[0-9a-f]{40}', build_id):
        raise ValueError('expected a separate candidate build ID')
    if report['release'] != release:
        raise ValueError('candidate release differs from the tested launcher contract')
    static_arm64(init)
    for name in ('Image', 'vim4.dtb', 'modules.tar.gz'):
        if sha(payload / name) != report['artifacts'][name]:
            raise ValueError('candidate artifact hash mismatch: ' + name)
    if state['release'] != baseline_release or state['build_id'] != baseline_id:
        raise ValueError('baseline proof release/build ID mismatch')
    if same_image:
        boot = '/boot/kernels/' + baseline_release
        if (baseline_release != formal_baseline()['release'] or not namespace or not payload_id or
                report['artifacts']['Image'] != state['files'].get(boot+'/Image') or
                report['artifacts']['vim4.dtb'] == state['files'].get(boot+'/vim4.dtb') or
                not report.get('dt_properties')):
            raise ValueError('same Image trial requires formal baseline proof, distinct DT, payload ID and DT properties')
        validate_distinct_dt(report['dt_properties'], state.get('dt_properties', {}))
        for path, expected in report['dt_properties'].items():
            node, _, prop = path.rpartition('/')
            actual = subprocess.check_output(['fdtget', '-t', 'bx', str(payload / 'vim4.dtb'),
                                              '/' + node.lstrip('/'), prop], text=True)
            if bytes.fromhex(actual).hex() != expected:
                raise ValueError('candidate DT property mismatch: ' + path)
    if '-npu' in release or release in ('7.3.0-vim4kvm-uhd2+', '7.3.0-vim4kvm-uhd2-nodebug+', '7.3.0-vim4kvm-uhd3+', '7.3.0-vim4kvm-uhd4+'):
        runtime = json.loads((payload / 'runtime-files.json').read_text())
        required = {'/usr/libexec/vim4-board-runtime', '/usr/libexec/vim4-kvm-run',
                    '/usr/libexec/vim4-mainline-prepare',
                    '/usr/libexec/vim4-mainline-gadget-prepare',
                    '/opt/vim4-onekvm-edge/one-kvm-edge'}
        if {entry['target'] for entry in runtime['files'].values()} != required:
            raise ValueError('incomplete NPU runtime helper inventory')
        for relative, entry in runtime['files'].items():
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('unsafe runtime helper path')
            if (sha(payload / relative) != entry['sha256'] or
                    state['files'].get(entry['target']) != entry['sha256']):
                raise ValueError('NPU runtime helper differs from baseline proof')
    required = {'/boot/extlinux/extlinux.conf', '/etc/vim4-kvm/kernels.json',
                '/etc/vim4-kvm/runtime-build.json'}
    if not baseline_release.startswith('5.15.'):
        boot = '/boot/kernels/'+baseline_release
        required.update((boot+'/Image', boot+'/vim4.dtb'))
    if not required.issubset(state['files']):
        raise ValueError('baseline proof must include boot and runtime registration files')
    cmdline = state['cmdline'].strip()
    if any(c in cmdline for c in '\r\n$;') or any(
            token.startswith(('init=', 'rdinit=')) for token in cmdline.split()):
        raise ValueError('unexpected baseline command line')
    layout = {} if namespace is None and payload_id is None else dict(namespace=namespace, payload_id=payload_id)
    prefix = str(candidate_prefix(dict(layout, build_id=build_id), 'trial.json'))
    if layout and (str(Path(prefix).parent) + '/').encode() + b'\0' not in init.read_bytes():
        raise ValueError('static init TRIAL_ROOT does not match payload namespace')
    candidate_cmdline = trial_cmdline(state)
    if '-npu' in release or release in ('7.3.0-vim4kvm-uhd2+', '7.3.0-vim4kvm-uhd2-nodebug+', '7.3.0-vim4kvm-uhd3+', '7.3.0-vim4kvm-uhd4+'):
        # Qualified uhd1 memory placement, absent from the vendor 5.15 cmdline.
        candidate_cmdline = ' '.join(token for token in candidate_cmdline.split()
                                     if not token.startswith(('cma=', 'modprobe.blacklist=')))
        candidate_cmdline += (' cma=512M@0x10000000-0xf0000000'
                              ' modprobe.blacklist=crg_udc,t7_hdmirx,t7_vdin_test,wave5')
        # udev coldplug precedes the HDMI service. kmod reads these options on
        # its first insertion; later modprobe calls cannot change loaded params.
        video_options = ('t7_hdmirx.edid_firmware=vim4-hdmirx-ddc-test/'
                         'uhd60-hdr10-audio-edid.bin ' + ' '.join(
                             't7_hdmirx.' + name + '=1' for name in (
                                 'phy_test', 'core_test', 'uhd60', 'dynamic_modes',
                                 'audio_test', 'hdr_probe', 'hdr_capture')) +
                         ' t7_vdin_test.nv12=1 t7_vdin_test.direct_dma=1')
        candidate_cmdline += ' ' + video_options
    config = (f'DEFAULT display-once\nTIMEOUT 1\nLABEL display-once\n'
              f'  LINUX {prefix}/Image\n  FDT {prefix}/vim4.dtb\n'
              f'  APPEND {candidate_cmdline} oops=panic panic=20 init={prefix}/init\n')
    with (payload / 'Image').open('rb') as image:
        command = trial_boot_command(prefix, (payload / 'Image').stat().st_size, image.read(64))
    output.mkdir()  # Refuse reuse of an earlier build's bundle.
    with tempfile.TemporaryDirectory(dir=output) as directory:
        work = Path(directory)
        for name in ('Image', 'vim4.dtb'):
            shutil.copyfile(payload / name, work / name)
        shutil.copyfile(init, work / 'init')
        (work / 'extlinux.conf').write_text(config)
        files = {name: sha(work / name) for name in ('Image', 'vim4.dtb', 'init', 'extlinux.conf')}
        plan = dict(build_id=build_id, baseline_id=baseline_id, release=release,
                    baseline_release=baseline_release,
                    baseline_files=state['files'], baseline_cmdline=cmdline,
                    files=files, command=command, source=report['source'])
        plan.update(layout)
        if same_image:
            plan['dt_properties'] = report['dt_properties']
            plan['baseline_dt_properties'] = {name: state['dt_properties'][name]
                                               for name in report['dt_properties']}
        if any(token.startswith('root=UUID=') for token in cmdline.split()):
            plan['root_partuuid'] = state['root_partuuid']
        with tarfile.open(payload / 'modules.tar.gz') as modules, \
                tarfile.open(output / 'candidate.tar', 'w') as archive:
            seen = set()
            for member in modules:
                path = safe_member(member)
                if path.parts[0] != release:
                    raise ValueError('unexpected module release')
                if member.isdir():
                    continue
                relative = str(PurePosixPath(*path.parts[1:]))
                if relative in seen or relative not in report['modules']:
                    raise ValueError('duplicate/unlisted module file: ' + relative)
                seen.add(relative)
                # Keep case-distinct kernel modules inside tar, including on macOS.
                with modules.extractfile(member) as source:
                    data = source.read()
                if hashlib.sha256(data).hexdigest() != report['modules'][relative]:
                    raise ValueError('module hash mismatch: ' + relative)
                member.name = 'modules/' + str(path)
                member.uid = member.gid = 0
                member.mode = 0o444
                archive.addfile(member, io.BytesIO(data))
                files[member.name] = report['modules'][relative]
            if seen != set(report['modules']):
                raise ValueError('module archive is incomplete')
            for name in ('Image', 'vim4.dtb', 'init', 'extlinux.conf'):
                archive.add(work / name, arcname=name)
            (work / 'trial.json').write_text(json.dumps(plan, indent=2) + '\n')
            archive.add(work / 'trial.json', arcname='trial.json')
        (output / 'trial.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(command)


def running_build_id():
    data = Path('/sys/kernel/notes').read_bytes()
    offset, ids = 0, []
    while offset + 12 <= len(data):
        name, desc, kind = struct.unpack_from('<III', data, offset)
        offset += 12
        end = offset + ((name + 3) & ~3) + ((desc + 3) & ~3)
        if end > len(data):
            raise ValueError('truncated running kernel notes')
        if data[offset:offset + name] == b'GNU\0' and kind == 3:
            start = offset + ((name + 3) & ~3)
            ids.append(data[start:start + desc].hex())
        offset = end
    if len(ids) != 1:
        raise ValueError('expected one running kernel build ID')
    return ids[0]


def preflight(plan):
    if (os.geteuid() or not supported_baseline(os.uname().release)
            or os.uname().release != plan['baseline_release']
            or running_build_id() != plan['baseline_id']):
        raise RuntimeError('stage only as root on the approved running baseline')
    validate_release(plan['release'])
    if not re.fullmatch(r'[0-9a-f]{40}', plan['baseline_id']):
        raise ValueError('bundle baseline mismatch')
    if Path('/proc/cmdline').read_text().strip() != plan['baseline_cmdline']:
        raise RuntimeError('baseline command line changed')
    if 'root_partuuid' in plan:
        partuuid = plan['root_partuuid']
        validate_partuuid(partuuid)
        if Path('/dev/disk/by-partuuid', partuuid).stat().st_rdev != Path('/').stat().st_dev:
            raise RuntimeError('root partition differs from baseline proof')
    for name, expected in plan['baseline_files'].items():
        if sha(name) != expected:
            raise RuntimeError('baseline file changed: ' + name)


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def retained_preflight(plan, state):
    """A chained trial retains the original recovery target on disk.

    The first window records this proof while running the baseline. Later candidates
    cannot match its running release/cmdline, but must preserve its exact files.
    """
    if (os.geteuid() or not supported_baseline(state['release']) or
            state['release'] != plan['baseline_release'] or
            state['build_id'] != plan['baseline_id'] or
            state['cmdline'] != plan['baseline_cmdline'] or
            state['files'] != plan['baseline_files']):
        raise RuntimeError('retained baseline differs from the approved trial proof')
    for name, expected in persistent_baseline_files(state['files']).items():
        if sha(name) != expected:
            raise RuntimeError('retained baseline file changed: ' + name)


def read_trial(archive, baseline=None):
    """Normalize existing trial.json and HDR2 manifest.json RAM payloads."""
    entries = {}
    for member in archive.getmembers():
        if member.isdir() and member.name in ('.', './'):
            continue
        name = str(safe_member(member))
        if member.isdir():
            continue
        if name in entries:
            raise ValueError('duplicate trial file: ' + name)
        entries[name] = member
    metadata = 'trial.json' if 'trial.json' in entries else 'manifest.json'
    report = json.load(archive.extractfile(entries[metadata]))
    if metadata == 'trial.json':
        plan = report
    else:
        validate_release(report['release'])
        plan = dict(release=report['release'], build_id=report['build_id'],
                    files=report['sha256'], source=report['source_commit'])
        for key in ('namespace', 'payload_id'):
            if key in report:
                plan[key] = report[key]
        if 'dt_properties' in report:
            plan['dt_properties'] = report['dt_properties']
        if 'baseline_dt_properties' in report:
            plan['baseline_dt_properties'] = report['baseline_dt_properties']
        if baseline is not None:
            plan.update(baseline_release=baseline['release'], baseline_id=baseline['build_id'],
                        baseline_cmdline=baseline['cmdline'], baseline_files=baseline['files'])
        prefix = str(candidate_prefix(plan, metadata))
        if 'Image' not in entries:
            raise ValueError('missing boot Image')
        with archive.extractfile(entries['Image']) as image:
            plan['command'] = trial_boot_command(prefix, entries['Image'].size, image.read(64))
        config = archive.extractfile(entries['extlinux.conf']).read().decode()
        for directive in (f'LINUX {prefix}/Image', f'FDT {prefix}/vim4.dtb', f'init={prefix}/init'):
            if directive not in config:
                raise ValueError('HDR2 config does not use the private RAM payload: ' + directive)
    validate_release(plan['release'])
    if baseline is not None and plan['build_id'] == baseline['build_id']:
        boot = '/boot/kernels/' + baseline['release']
        if (baseline['release'] != formal_baseline()['release'] or not plan.get('namespace') or
                not plan.get('payload_id') or not plan.get('dt_properties') or
                plan['files']['Image'] != baseline['files'].get(boot+'/Image') or
                plan['files']['vim4.dtb'] == baseline['files'].get(boot+'/vim4.dtb')):
            raise ValueError('same Image payload requires formal baseline proof and distinct DT identity')
        validate_distinct_dt(plan['dt_properties'], baseline.get('dt_properties', {}))
        if 'baseline_dt_properties' in plan and any(
                baseline['dt_properties'].get(name) != value
                for name, value in plan['baseline_dt_properties'].items()):
            raise ValueError('DT identity was prepared for different baseline properties')
        prefix = '/lib/modules/' + plan['release'] + '/'
        expected = {name.removeprefix(prefix): value for name, value in baseline['files'].items()
                    if name.startswith(prefix)}
        candidate = {name.removeprefix('modules/' + plan['release'] + '/'): value
                     for name, value in plan['files'].items() if name.startswith('modules/' + plan['release'] + '/')}
        if not expected or candidate != expected:
            raise ValueError('same Image payload must preserve the complete baseline module set')
    prefix = str(candidate_prefix(plan, metadata))
    if 'Image' not in entries:
        raise ValueError('missing boot Image')
    with archive.extractfile(entries['Image']) as image:
        command = trial_boot_command(prefix, entries['Image'].size, image.read(64))
    if 'namespace' in plan:
        if plan['command'] != command:
            raise ValueError('candidate command does not match payload namespace or Image load layout')
        config = archive.extractfile(entries['extlinux.conf']).read().decode()
        for directive in (f'LINUX {prefix}/Image', f'FDT {prefix}/vim4.dtb', f'init={prefix}/init'):
            if directive not in config:
                raise ValueError('config does not match payload namespace')
        init = archive.extractfile(entries['init']).read()
        if (str(Path(prefix).parent) + '/').encode() + b'\0' not in init:
            raise ValueError('static init TRIAL_ROOT does not match payload namespace')
    if not re.fullmatch('[0-9a-f]{40}', plan['build_id']):
        raise ValueError('invalid destination build ID')
    if set(entries) != {*plan['files'], metadata}:
        raise ValueError('trial archive inventory mismatch')
    if not {'Image', 'vim4.dtb', 'init', 'extlinux.conf'} <= set(plan['files']):
        raise ValueError('missing boot artifacts')
    return plan, metadata, entries


def stage(bundle, retained_baseline=None, reuse_staged=False):
    def ensure_mountpoint(directory):
        # HDR2 uses a distinct release but its static PID 1 still needs
        # an existing empty bind destination; never install modules here.
        if metadata == 'manifest.json' or 'namespace' in plan:
            mountpoint = MODULE_ROOT / plan['release']
            if not mountpoint.exists():
                mountpoint.mkdir(mode=0o755)
                (directory / '.created-module-mountpoint.json').write_text('{}\n')

    def check(plan):
        if retained_baseline is None:
            preflight(plan)
        else:
            retained_preflight(plan, retained_baseline)
    with tarfile.open(bundle) as archive:
        plan, metadata, entries = read_trial(archive, retained_baseline)
        if metadata == 'manifest.json' and retained_baseline is None:
            raise ValueError('HDR2 payload requires original retained baseline proof')
        check(plan)
        stage_root = candidate_parent(plan, metadata)
        # An interrupted extraction is inert: no boot path points at this directory.
        stage_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        target = stage_root / plan['build_id']
        if target.exists() or target.is_symlink():
            if not reuse_staged or target.is_symlink() or not target.is_dir():
                raise FileExistsError(target)
            # Performance A/B/A revisits an immutable candidate. Never overwrite
            # its payload: verify every archived file before selecting it again.
            for name, member in entries.items():
                digest = plan['files'][name] if name != metadata else hashlib.sha256(archive.extractfile(member).read()).hexdigest()
                if sha(target / name) != digest:
                    raise ValueError('staged trial file hash mismatch: ' + name)
            static_arm64(target / 'init')
            check(plan)
            ensure_mountpoint(target)
            print('REUSED_VERIFIED', target)
            return
        with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=stage_root) as directory:
            work = Path(directory)
            for name, member in entries.items():
                destination = work / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open('xb') as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                executable = name == 'init' or ((metadata == 'manifest.json' or 'namespace' in plan) and member.mode & 0o111)
                destination.chmod(0o555 if executable else 0o444)
                if name != metadata and sha(destination) != plan['files'][name]:
                    raise ValueError('trial file hash mismatch: ' + name)
            static_arm64(work / 'init')
            for path in sorted(work.rglob('*'), reverse=True):
                if path.is_dir():
                    path.chmod(0o555)
                    fsync_directory(path)
            # Recheck baseline just before publication; never select a trial here.
            check(plan)
            ensure_mountpoint(work)
            work.chmod(0o555)
            fsync_directory(work)
            work.rename(target)
            fsync_directory(stage_root)
    print('STAGED_ONLY', target)
    print(plan['command'])


def cleanup_module_mountpoint(plan):
    """Remove only our still-empty original bind destination after baseline return."""
    validate_release(plan['release'])
    if os.geteuid() or not supported_baseline(os.uname().release):
        raise RuntimeError('module mountpoint cleanup requires root on 5.15 or the formal baseline')
    if not re.fullmatch('[0-9a-f]{40}', plan['build_id']):
        raise ValueError('invalid destination build ID')
    marker = candidate_prefix(plan) / '.created-module-mountpoint.json'
    if not marker.exists():
        return
    path = MODULE_ROOT / plan['release']
    if path.exists():
        path.rmdir()  # Nonempty or still-mounted directories fail and are preserved.
    marker.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prepare_parser = commands.add_parser('prepare')
    for name in ('payload', 'init', 'baseline', 'output'):
        prepare_parser.add_argument('--' + name, type=Path, required=True)
    prepare_parser.add_argument('--release', default=RELEASE)
    prepare_parser.add_argument('--baseline-release', help='Defaults to the captured baseline proof')
    prepare_parser.add_argument('--baseline-id', help='Defaults to the captured baseline proof')
    prepare_parser.add_argument('--namespace')
    prepare_parser.add_argument('--payload-id')
    stage_parser = commands.add_parser('stage')
    stage_parser.add_argument('bundle', type=Path)
    stage_parser.add_argument('--retained-baseline', type=lambda p: json.loads(Path(p).read_text()),
                              help='original baseline proof for chained RAM trials')
    args = vars(parser.parse_args())
    action = args.pop('action')
    (prepare if action == 'prepare' else stage)(**args)


if __name__ == '__main__':
    main()
