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
import tarfile
import tempfile

RELEASE = '7.3.0-vim4kvm-uhd1+'
BASE_ID = '7b8372b894c98ffae12e636a325c86f2b6c85e00'
ROOT = Path('/var/lib/vim4-kvm/display-m1')


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


def prepare(payload, init, baseline, output, release=RELEASE,
            baseline_release=RELEASE, baseline_id=BASE_ID):
    if not re.fullmatch(r'7\.3\.0-vim4kvm-(?:uhd1|npu[0-9]+)\+', release):
        raise ValueError('unsupported candidate release')
    if not re.fullmatch(r'[0-9a-f]{40}', baseline_id):
        raise ValueError('baseline build ID must be explicit and complete')
    report = json.loads((payload / 'manifest.json').read_text())
    build_id = report['kernel_build_id']
    if not re.fullmatch('[0-9a-f]{40}', build_id) or build_id == baseline_id:
        raise ValueError('expected a separate candidate build ID')
    if report['release'] != release:
        raise ValueError('candidate release differs from the tested launcher contract')
    static_arm64(init)
    for name in ('Image', 'vim4.dtb', 'modules.tar.gz'):
        if sha(payload / name) != report['artifacts'][name]:
            raise ValueError('candidate artifact hash mismatch: ' + name)
    state = json.loads(baseline.read_text())
    if '-npu' in release:
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
    if not all(name in state['files'] for name in
               ('/boot/edge/Image', '/boot/edge/vim4.dtb', '/boot/extlinux/extlinux.conf',
                '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json')):
        raise ValueError('baseline proof must include boot and runtime registration files')
    cmdline = state['cmdline'].strip()
    if any(c in cmdline for c in '\r\n$;') or any(
            token.startswith(('init=', 'rdinit=')) for token in cmdline.split()):
        raise ValueError('unexpected baseline command line')
    prefix = str(ROOT / build_id)
    config = (f'DEFAULT display-once\nTIMEOUT 1\nLABEL display-once\n'
              f'  LINUX {prefix}/Image\n  FDT {prefix}/vim4.dtb\n'
              f'  APPEND {cmdline} oops=panic panic=20 init={prefix}/init\n')
    command = f'sysboot mmc 1:2 any ${{pxefile_addr_r}} {prefix}/extlinux.conf; reset'
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
    if (os.geteuid() or os.uname().release != plan.get('baseline_release', RELEASE)
            or running_build_id() != plan['baseline_id']):
        raise RuntimeError('stage only as root on the approved running baseline')
    if (not re.fullmatch(r'[0-9a-f]{40}', plan['baseline_id']) or
            not re.fullmatch(r'7\.3\.0-vim4kvm-(?:uhd1|npu[0-9]+)\+', plan['release'])):
        raise ValueError('bundle baseline mismatch')
    if Path('/proc/cmdline').read_text().strip() != plan['baseline_cmdline']:
        raise RuntimeError('baseline command line changed')
    for name, expected in plan['baseline_files'].items():
        if sha(name) != expected:
            raise RuntimeError('baseline file changed: ' + name)


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage(bundle):
    with tarfile.open(bundle) as archive:
        plan = json.load(archive.extractfile('trial.json'))
        if not re.fullmatch('[0-9a-f]{40}', plan['build_id']):
            raise ValueError('invalid destination build ID')
        preflight(plan)
        ROOT.mkdir(parents=True, exist_ok=True, mode=0o755)
        # An interrupted extraction is inert: no boot path points at this directory.
        for ancestor in (ROOT, *ROOT.parents):
            info = ancestor.lstat()
            if not ancestor.is_dir() or ancestor.is_symlink() or info.st_uid or info.st_mode & 0o022:
                raise RuntimeError('untrusted staging ancestor: ' + str(ancestor))
        target = ROOT / plan['build_id']
        if target.exists():
            raise FileExistsError(target)
        with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=ROOT) as directory:
            work = Path(directory)
            seen = set()
            for member in archive:
                name = str(safe_member(member))
                if member.isdir():
                    continue
                if name in seen or name not in {*plan['files'], 'trial.json'}:
                    raise ValueError('duplicate/unlisted trial file: ' + name)
                seen.add(name)
                destination = work / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open('xb') as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                destination.chmod(0o555 if name == 'init' else 0o444)
                if name != 'trial.json' and sha(destination) != plan['files'][name]:
                    raise ValueError('trial file hash mismatch: ' + name)
            if seen != {*plan['files'], 'trial.json'}:
                raise ValueError('trial archive is incomplete')
            static_arm64(work / 'init')
            for path in sorted(work.rglob('*'), reverse=True):
                if path.is_dir():
                    path.chmod(0o555)
                    fsync_directory(path)
            work.chmod(0o555)
            fsync_directory(work)
            # Recheck baseline just before publication; never select a trial here.
            preflight(plan)
            work.rename(target)
            fsync_directory(ROOT)
    print('STAGED_ONLY', target)
    print(plan['command'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prepare_parser = commands.add_parser('prepare')
    for name in ('payload', 'init', 'baseline', 'output'):
        prepare_parser.add_argument('--' + name, type=Path, required=True)
    prepare_parser.add_argument('--release', default=RELEASE)
    prepare_parser.add_argument('--baseline-release', default=RELEASE)
    prepare_parser.add_argument('--baseline-id', default=BASE_ID)
    commands.add_parser('stage').add_argument('bundle', type=Path)
    args = vars(parser.parse_args())
    action = args.pop('action')
    (prepare if action == 'prepare' else stage)(**args)


if __name__ == '__main__':
    main()
