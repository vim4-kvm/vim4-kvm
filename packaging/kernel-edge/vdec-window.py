#!/usr/bin/env python3
"""Prepare or run one supervised decoder window; default is offline plan only.

Run on Mac. --execute requires --at-board and a matched candidate manifest.
Boot actions install the candidate and arm baseline recovery. Reboots and
functional baseline checks are supervised steps described in the bringup record.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tarfile


BOOT_ACTIONS = ('boot-install', 'arm-baseline', 'verify-baseline')
ACTIONS = (*BOOT_ACTIONS, 'probe', 'power', 'compliance', 'h264', 'wave')
BASE_ID = 'f283ab1f8a001a19bab5247afc4f9b0c00c1da99'
BASE_RELEASE = '7.3.0-vim4kvm-uhd1+'
BASE_FILES = {
    'Image': '855f0fa8caa49fdb9973bd7cd1cbbfaa2c5f62138574862e651e16eb0fda42b5',
    'vim4.dtb': 'd2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6',
}
FAILED_SOURCE = '5bf7d6359df9ff68d8746851cf45de40611988a1'


def require_candidate(action, proof):
    if not proof['release'].startswith('7.3.0-vim4kvm-vdec3'):
        raise ValueError('Only this separate experimental kernel is accepted')
    if action not in ('arm-baseline', 'verify-baseline') and proof.get('source') == FAILED_SOURCE:
        raise ValueError('Known failing candidate: udev v4l_id caused SError during DOS power-up; '
                         'prepare a revised offline candidate before another board window')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_baseline_files():
    for name, expected in BASE_FILES.items():
        if sha(Path('/boot/edge') / name) != expected:
            raise ValueError('Baseline boot file mismatch: ' + name)


def require_services():
    for name in ('one-kvm', 'vim4-manager'):
        if run('systemctl', 'is-active', name).strip() != 'active':
            raise ValueError('Baseline service is not active: ' + name)


def boot_window(args):
    """Never reboot automatically; arm baseline boot files before codec MMIO."""
    backup, payload = Path(args.backup), Path(args.payload)
    if args.action == 'boot-install':
        if os.uname().release != BASE_RELEASE or build_id('/sys/kernel/notes') != BASE_ID:
            raise ValueError('Wait for other tasks to restore the retained baseline')
        require_baseline_files()
        require_services()
        sys.path.insert(0, '/usr/lib/vim4-kvm/python')
        import vim4boot
        config = Path('/boot/extlinux/extlinux.conf').read_text()
        selected = vim4boot.boot_entries(config)[vim4boot.default_label(config)]
        if selected.get('LINUX') != '/edge/Image' or selected.get('FDT') != '/edge/vim4.dtb':
            raise ValueError('Default boot entry does not use the retained edge paths')
        proof = json.loads((payload / 'manifest.json').read_text())
        release = proof['release']
        if not release.startswith('7.3.0-vim4kvm-vdec3') or proof['kernel_build_id'] != args.build_id:
            raise ValueError('Staged manifest does not match the local candidate')
        for name, expected in proof['artifacts'].items():
            if Path(name).name != name or sha(payload / name) != expected:
                raise ValueError('Candidate artifact mismatch: ' + name)
        modules = Path('/lib/modules') / release
        if modules.exists():
            raise ValueError('Refusing to replace existing candidate modules')
        if shutil.disk_usage('/').free < 2 * (payload / 'modules.tar.gz').stat().st_size + 400_000_000:
            raise ValueError('Insufficient rootfs space for fresh backup and modules')
        if (shutil.disk_usage('/boot').free + Path('/boot/edge/Image').stat().st_size <
                (payload / 'Image').stat().st_size + 4_000_000):
            raise ValueError('Insufficient boot space for candidate replacement')
        # Refuse active virtual media before the reboot disconnects the host.
        for path in Path('/sys/kernel/config/usb_gadget').glob('*/functions/mass_storage.*/lun.*/file'):
            if path.read_text().strip():
                raise ValueError('Safely eject active virtual media before this window')
        backup.mkdir(mode=0o700)
        for name in BASE_FILES:
            shutil.copy2(Path('/boot/edge') / name, backup / name)
        (backup / 'baseline.json').write_text(json.dumps(BASE_FILES) + '\n')
        os.sync()
        stage = backup / 'staging'
        stage.mkdir()
        with tarfile.open(payload / 'modules.tar.gz') as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts
                if (not parts or parts[0] != release or '..' in parts or
                        not (member.isfile() or member.isdir())):
                    raise ValueError('Unsafe module archive member')
        run('tar', '-xzf', str(payload / 'modules.tar.gz'), '-C', str(stage), timeout=90)
        actual = {str(p.relative_to(stage / release)): sha(p)
                  for p in (stage / release).rglob('*') if p.is_file()}
        if actual != proof['modules']:
            raise ValueError('Extracted module inventory differs')
        run('systemctl', 'stop', 'one-kvm', timeout=20)
        try:
            (stage / release).rename(modules)
            # FAT /boot has room for one Image: retain its backup on rootfs.
            for name in BASE_FILES:
                target = Path('/boot/edge') / name
                target.unlink()
                shutil.copy2(payload / name, target)
            os.sync()
        except BaseException:
            for name in BASE_FILES:
                shutil.copy2(backup / name, Path('/boot/edge') / name)
            os.sync()
            run('systemctl', 'start', 'one-kvm', timeout=20)
            raise
        print('CANDIDATE_INSTALLED: reboot once under both locks; then arm-baseline BEFORE probe', flush=True)
    elif args.action == 'arm-baseline':
        if build_id('/sys/kernel/notes') != args.build_id:
            raise ValueError('Expected the running candidate before arming recovery')
        for name, expected in BASE_FILES.items():
            if sha(backup / name) != expected:
                raise ValueError('Fresh baseline backup mismatch: ' + name)
        for name in BASE_FILES:
            target = Path('/boot/edge') / name
            target.unlink()
            shutil.copy2(backup / name, target)
        os.sync()
        require_baseline_files()
        print('BASELINE_ARMED: next reboot or RESET boots the retained baseline', flush=True)
    else:
        if os.uname().release != BASE_RELEASE or build_id('/sys/kernel/notes') != BASE_ID:
            raise ValueError('Retained baseline is not running')
        require_baseline_files()
        require_services()
        if not any(p.read_text().strip() == 'configured' for p in Path('/sys/class/udc').glob('*/state')):
            raise ValueError('USB UDC is not configured')
        print('BASELINE_BOOT_SERVICES_UDC_OK', BASE_ID, flush=True)
        print('STILL_REQUIRED: actual HID event + H264 encode + HDMI frame verification', flush=True)


def run(*command, timeout=15):
    print('RUN', json.dumps(command), flush=True)
    result = subprocess.run(command, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=timeout)
    print(result.stdout, end='', flush=True)
    result.check_returncode()
    return result.stdout


def build_id(path):
    data = Path(path).read_bytes()
    offset = 0
    while offset + 12 <= len(data):
        namesz, descsz, kind = struct.unpack_from('<III', data, offset)
        offset += 12
        name = data[offset:offset + namesz].rstrip(b'\0')
        offset += (namesz + 3) & ~3
        value = data[offset:offset + descsz]
        offset += (descsz + 3) & ~3
        if name == b'GNU' and kind == 3:
            return value.hex()
    raise ValueError('Missing kernel build ID')


def faulted():
    return any(path.read_text().strip() == '1' for path in
               Path('/sys/bus/platform/devices').glob('*/faulted'))


def video_node(decoder):
    for path in Path('/sys/class/video4linux').glob('video*/name'):
        name = path.read_text().strip()
        if (decoder == 'wave' and 'Wave5 VPU decoder' in name or
                decoder == 'h264' and name == 'aml_dev_drv'):
            return '/dev/' + path.parent.name
    raise ValueError('Decoder video node missing')


def board_window(args):
    if os.geteuid() != 0:
        raise ValueError('Board subprocess requires root')
    if args.action in BOOT_ACTIONS:
        boot_window(args)
        return
    if Path('/tmp/vim4-vdec-reset-required').exists():
        raise ValueError('Previous window requires supervised reset and baseline recovery')
    if build_id('/sys/kernel/notes') != args.build_id:
        raise ValueError('Running kernel does not match candidate')
    require_baseline_files()
    print('CANDIDATE_RUNNING', args.build_id, args.action, flush=True)
    clip = Path(args.fixtures) / 'small.h264'
    reference = Path(args.fixtures) / 'small.i420'
    if args.action in ('h264', 'wave'):
        info = json.loads(run('ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                              '-of', 'json', str(clip)))['streams'][0]
        if (info['codec_name'], info['width'], info['height'], info['pix_fmt'],
                info['nb_read_frames']) != ('h264', 320, 256, 'yuv420p', '6'):
            raise ValueError('Only the six-frame 320x256 8-bit fixture is allowed')
        hashes = json.loads((Path(args.fixtures) / 'fixtures.json').read_text())
        for name in ('small.h264', 'small.i420'):
            if hashlib.sha256((Path(args.fixtures) / name).read_bytes()).hexdigest() != hashes[name]:
                raise ValueError('Fixture hash mismatch: ' + name)
        factory = 'v4l2h264dec' if args.action == 'wave' else 'v4l2slh264dec'
        # The stateless factory appears only after its media device is registered.
        run('gst-inspect-1.0', 'videoconvert')
    service_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'one-kvm']).returncode == 0
    loaded = {name for name in ('wave5', 't7_jpeg') if Path('/sys/module', name).exists()}
    critical = False
    removed = []
    candidate = None
    try:
        run('systemctl', 'stop', 'one-kvm')
        owners = []
        for path in Path('/proc').glob('[0-9]*/fd/*'):
            try:
                if str(path.readlink()).startswith(('/dev/video', '/dev/jpegenc')):
                    owners.append(str(path))
            except OSError:
                pass
        if owners:
            raise ValueError('Video users still active: ' + repr(owners))
        # The kernel lease also excludes raw DOS/firmware/reset concurrency.
        for name in ('aml_vdec_drv', 'wave5', 't7_jpeg'):
            if Path('/sys/module', name).exists():
                if faulted():
                    raise RuntimeError('Decoder DMA quarantine is active')
                run('modprobe', '-r', name)
                removed.append(name)
        if args.action == 'wave':
            run('modprobe', 'wave5', 't7_decode_test=1')
            candidate = 'wave5'
        else:
            run('modprobe', 'aml-vdec-drv', 'enable_t7=1')
            candidate = 'aml_vdec_drv'
        if args.action == 'probe':
            # Registration can trigger udev v4l_id opens. The driver must gate
            # power independently before probe can be a stage without DOS MMIO.
            print('PROBE_REGISTERED', video_node('h264'), flush=True)
            if faulted():
                raise RuntimeError('Fault reported at probe')
        elif args.action == 'power':
            run('v4l2-ctl', '-d', video_node('h264'), '--info', timeout=8)
            for path in Path('/sys/bus/platform/devices').glob('*/faulted'):
                status = (path.parent / 'power/runtime_status').read_text().strip()
                print('RUNTIME_AFTER_CLOSE', path.parent.name, status,
                      'faulted=' + path.read_text().strip(), flush=True)
                if status != 'suspended':
                    critical = True
                    raise RuntimeError('Runtime PM did not suspend after close')
        elif args.action == 'compliance':
            run('v4l2-compliance', '-d', video_node('h264'), timeout=20)
        else:
            video_node('wave' if args.action == 'wave' else 'h264')
            output = Path('/tmp/vim4-vdec-' + args.action + '.i420')
            factory = 'v4l2h264dec' if args.action == 'wave' else 'v4l2slh264dec'
            run('gst-inspect-1.0', factory, timeout=8)
            run('gst-launch-1.0', '-q', 'filesrc', 'location=' + str(clip), '!',
                'h264parse', '!', factory, '!', 'videoconvert', '!',
                'video/x-raw,format=I420,width=320,height=256', '!',
                'filesink', 'location=' + str(output), timeout=10)
            if output.read_bytes() != reference.read_bytes():
                raise ValueError('Decoded frames differ from software reference')
            print('EXACT_FRAMES_MATCH', hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)
        if faulted():
            raise RuntimeError('DMA stop not confirmed')
    except subprocess.TimeoutExpired:
        critical = True
        raise
    except (RuntimeError, subprocess.CalledProcessError):
        critical = critical or faulted() or args.action == 'wave'
        raise
    finally:
        if critical or faulted():
            Path('/tmp/vim4-vdec-reset-required').write_text('Do not reload codecs. Restore boot baseline and reset.\n')
            print('RESET_REQUIRED: retain DMA; no unload/reload or automatic retry', flush=True)
        else:
            try:
                if candidate and Path('/sys/module', candidate).exists():
                    run('modprobe', '-r', candidate)
                for name in sorted(loaded.intersection(removed)):
                    run('modprobe', name)
                if service_active:
                    run('systemctl', 'start', 'one-kvm')
                print('CANDIDATE_WINDOW_RESTORED; baseline boot and HID checks still required', flush=True)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                Path('/tmp/vim4-vdec-reset-required').write_text('Cleanup failed; restore boot baseline under supervision.\n')
                print('RECOVERY_REQUIRED: cleanup failed; stop this sequence and restore baseline', flush=True)
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--fixtures', default='/var/tmp/vim4-vdec-fixtures')
    parser.add_argument('--payload', default='/var/tmp/vim4-vdec-r3')
    parser.add_argument('--backup', default='/var/backups/vim4-vdec-r3-20261022')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--at-board', action='store_true')
    parser.add_argument('--locked', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--remote', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--build-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.remote:
        # Keep missing diagnostic tools in the temporary payload, off the rootfs
        # package database. Their shared libraries are checked before installation.
        tool_bin = Path(args.payload) / 'tools/usr/bin'
        if tool_bin.is_dir():
            os.environ['PATH'] = str(tool_bin) + os.pathsep + os.environ['PATH']
        board_window(args)
        return
    if not args.execute:
        print(json.dumps({'action': args.action, 'offline': True, 'ssh': False,
                          'order': ['board + heavy locks', 'boot-install, reboot, arm-baseline',
                                    'stop clients', 'exclusive codec lease', args.action,
                                    'safe unload or RESET_REQUIRED', 'restore boot baseline',
                                    'encoding + HDMI + services + UDC + actual HID verification']}, indent=2))
        return
    if not args.at_board or args.manifest is None:
        parser.error('--execute requires --at-board and --manifest')
    proof = json.loads(args.manifest.read_text())
    require_candidate(args.action, proof)
    if not args.locked:
        command = ['/usr/bin/lockf', '-t', '600', '/tmp/vim4-board.lock',
                   '/usr/bin/lockf', '-t', '120', '/tmp/vim4-heavy.lock',
                   sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--locked']
        subprocess.run(command, check=True)
        return
    source = Path(__file__).read_text()
    remote = ['sudo', 'python3', '-', args.action, '--remote',
              '--build-id', proof['kernel_build_id'], '--fixtures', args.fixtures,
              '--payload', args.payload, '--backup', args.backup]
    subprocess.run(['ssh', '-o', 'ConnectTimeout=8', 'vim4', shlex.join(remote)],
                   input=source, text=True, check=True, timeout=180)


if __name__ == '__main__':
    main()
