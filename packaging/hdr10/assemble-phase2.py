#!/usr/bin/env python3
"""Offline kernel archive + checked userspace overlay -> namespaced RAM payload.

Run on Linux ARM64 with a static compiler, under board-queue --heavy.
--dry-run allows the retained uhd5 package for assembly validation only.
No SSH, board access, firmware provisioning, installation or default changes.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('once', ROOT / 'kernel-edge/display-once.py')
once = importlib.util.module_from_spec(spec)
spec.loader.exec_module(once)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_archive(path, expected):
    if once.sha(path) != expected:
        raise ValueError('archive SHA mismatch: ' + str(path))
    result = {}
    with tarfile.open(path) as archive:
        for member in archive:
            if member.isdir(): continue
            name = str(once.safe_member(member))
            if name in result: raise ValueError('duplicate archive member')
            result[name] = archive.extractfile(member).read()
    return result


def verify_plugins(runtime):
    with tempfile.TemporaryDirectory() as temporary:
        directory=Path(temporary)
        for name,data in runtime.items():
            if name.startswith('gstreamer-1.0/'):
                path=directory/Path(name).name;path.write_bytes(data)
        return json.loads(subprocess.check_output([sys.executable,
            str(ROOT/'hdr10/check-phase2-plugins.py'),str(directory)],text=True))


def assemble(args):
    base = read_archive(args.kernel, args.kernel_sha256)
    report = json.loads(base['manifest.json'])
    release, build = report['release'], report['kernel_build_id']
    once.validate_release(release)
    for name, expected in report['files'].items():
        if digest(base[name]) != expected: raise ValueError('kernel inventory mismatch: ' + name)
    overlay = read_archive(args.userspace, args.userspace_sha256)
    user = json.loads(overlay.pop('manifest.json'))
    if set(overlay) != set(user['sha256']): raise ValueError('userspace inventory differs')
    for name, data in overlay.items():
        if digest(data) != user['sha256'][name]: raise ValueError('userspace hash mismatch')
    if not args.dry_run and not release.startswith('7.3.0-vim4kvm-uhd6'):
        raise ValueError('board candidate needs unified uhd6; uhd5 is dry-run only')
    plan = dict(namespace='hdr10', payload_id=args.payload_id, build_id=build)
    prefix = str(once.candidate_prefix(plan))
    parent = str(once.candidate_parent(plan)) + '/'
    files = {'Image': base['Image'], 'vim4.dtb': base[args.gpu + '.dtb'] if args.gpu == 'panfrost' else base['vim4.dtb']}
    runtime = {str(PurePosixPath(name).relative_to('runtime')): value
               for name, value in base.items() if name.startswith('runtime/')}
    bindings = {name: '/' + name for name in runtime}
    for name, target in {'one-kvm':'/opt/vim4-onekvm/one-kvm', 'nanokvm':'/opt/vim4-nanokvm/NanoKVM-Server',
            'jetkvm':'/opt/vim4-jetkvm/jetkvm', 'ustreamer':'/usr/bin/ustreamer',
            'libjanus_ustreamer.so':'/usr/lib/ustreamer/janus/libjanus_ustreamer.so'}.items():
        runtime[name] = overlay[name]; bindings[name] = target
    for name, value in overlay.items():
        if name.startswith('gstreamer-1.0/'): runtime[name] = value
    if 'gstreamer-1.0/libgstvim4jpegenc.so' not in overlay:
        raise ValueError('userspace bundle must include the pinned vim4jpegenc plugin')
    plugin_proof=verify_plugins(runtime)
    runtime['check-phase2-plugins.py']=(ROOT/'hdr10/check-phase2-plugins.py').read_bytes()
    bindings['gstreamer-1.0'] = '/usr/lib/vim4-kvm/mainline-gstreamer-1.0'
    # Candidate launcher selects GPU by the declared payload, never changes the
    # system ICD or reuses a different release's modules. Probe gates remain in apps.
    launcher = ROOT / 'hdr10/phase2-run'
    runtime['usr/libexec/vim4-kvm-run'] = launcher.read_bytes().replace(b'@PREFIX@', prefix.encode()).replace(b'@GPU@', args.gpu.encode())
    modules = {}
    with tarfile.open(fileobj=io.BytesIO(base['modules.tar.gz'])) as archive:
        for member in archive:
            if member.isdir(): continue
            path = once.safe_member(member)
            if path.parts[0] != release: raise ValueError('mixed module release')
            relative = str(PurePosixPath(*path.parts[1:]))
            data = archive.extractfile(member).read()
            if relative in modules or report['modules'].get(relative) != digest(data):
                raise ValueError('module inventory/hash mismatch')
            modules[relative] = digest(data)
            files['modules/' + str(path)] = data
    if modules != report['modules']: raise ValueError('incomplete module set')
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        header = 'const char *names[] = {' + ','.join(json.dumps(x) for x in bindings) + '};\n'
        header += 'const char *targets[] = {' + ','.join(json.dumps(x) for x in bindings.values()) + '};\n'
        (work / 'phase2-bindings.h').write_text(header)
        subprocess.run(['cc', '-static', '-O2', '-Wall', '-Wextra', '-Werror', '-DPHASE2_RUNTIME',
            '-DRELEASE=' + json.dumps(release), '-DTRIAL_ROOT=' + json.dumps(parent), '-I' + str(work),
            str(ROOT / 'hdr10/trial-init.c'), '-o', str(work / 'init')], check=True)
        once.static_arm64(work / 'init')
        files['init'] = (work / 'init').read_bytes()
    baseline = json.loads(args.baseline.read_text())
    state = baseline.get('identity', baseline)
    command = once.trial_cmdline(state)
    command = ' '.join(t for t in command.split() if not t.startswith(('cma=', 'modprobe.blacklist=')))
    command += ' cma=512M@0x10000000-0xf0000000 modprobe.blacklist=crg_udc,t7_hdmirx,t7_vdin_test,wave5'
    if args.gpu == 'kbase': command += ',panfrost'
    files['extlinux.conf'] = (f'DEFAULT phase2\nTIMEOUT 1\nLABEL phase2\n LINUX {prefix}/Image\n FDT {prefix}/vim4.dtb\n APPEND {command} oops=panic panic=20 init={prefix}/init\n').encode()
    files.update({'runtime/' + name: value for name, value in runtime.items()})
    manifest = dict(plan, release=release, source_commit=report['source'], hardware_validated=False,
        dry_run=args.dry_run, kernel_archive_sha256=args.kernel_sha256, userspace_sha256=args.userspace_sha256,
        module_count=sum('.ko' in name for name in modules), gpu=args.gpu,
        plugin_check=plugin_proof,
        sha256={name: digest(value) for name, value in files.items()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'x:gz') as archive:
        for name, data in {**files, 'manifest.json':(json.dumps(manifest, indent=2)+'\n').encode()}.items():
            info = tarfile.TarInfo(name); info.size=len(data); info.uid=info.gid=0
            info.mode=0o755 if name.startswith('runtime/') or name == 'init' else 0o644
            archive.addfile(info, io.BytesIO(data))
    with tarfile.open(args.output) as archive:
        checked, _, entries = once.read_trial(archive)
        for name, expected in checked['files'].items():
            if digest(archive.extractfile(entries[name]).read()) != expected: raise ValueError('assembled inventory mismatch')
    proof = dict(sha256=once.sha(args.output), release=release, build_id=build,
        modules=manifest['module_count'], dry_run=args.dry_run, gpu=args.gpu)
    args.output.with_suffix(args.output.suffix + '.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('kernel','userspace','baseline','output'): parser.add_argument('--'+name, type=Path, required=True)
    for name in ('kernel-sha256','userspace-sha256','payload-id'): parser.add_argument('--'+name, required=True)
    parser.add_argument('--gpu', choices=('kbase','panfrost'), required=True)
    parser.add_argument('--dry-run', action='store_true')
    assemble(parser.parse_args())
