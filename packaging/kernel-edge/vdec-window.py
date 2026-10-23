#!/usr/bin/env python3
"""Prepare or run one supervised decoder window; default is offline plan only.

Run on Mac. --execute requires --at-board or --once-baseline and a matched manifest.
The latter uses a watchdog-protected RAM boot and never writes default boot files.
Boot actions install the candidate and arm baseline recovery. Reboots and
functional baseline checks are supervised steps described in the bringup record.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import struct
import subprocess
import sys
import tarfile
import time


BOOT_ACTIONS = ('boot-install', 'arm-baseline', 'verify-baseline')
ACTIONS = (*BOOT_ACTIONS, 'probe', 'power', 'mdec', 'compliance', 'h264', 'h264-1080p', 'wave')
BASE_ID = 'f283ab1f8a001a19bab5247afc4f9b0c00c1da99'
BASE_RELEASE = '7.3.0-vim4kvm-uhd1+'
BASE_FILES = {
    'Image': '855f0fa8caa49fdb9973bd7cd1cbbfaa2c5f62138574862e651e16eb0fda42b5',
    'vim4.dtb': 'd2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6',
}
FAILED_SOURCES = {
    '5bf7d6359df9ff68d8746851cf45de40611988a1',
    '34ab72b7fbecaa13347aca58584b4bcb10b1b73e',
}


def require_candidate(action, proof, once=False):
    if once:
        if action in BOOT_ACTIONS:
            raise ValueError('One-time boot forbids persistent boot actions')
        if proof['release'] != BASE_RELEASE or proof.get('once') is not True:
            raise ValueError('Expected a private-module one-time boot package')
        if proof.get('source') in FAILED_SOURCES:
            raise ValueError('Known failing candidate')
        return
    recovery = action in ('arm-baseline', 'verify-baseline')
    if not proof['release'].startswith('7.3.0-vim4kvm-vdec5') and not (
            recovery and proof['release'].startswith(('7.3.0-vim4kvm-vdec3',
                                                       '7.3.0-vim4kvm-vdec4'))):
        raise ValueError('Only this separate experimental kernel is accepted')
    if not recovery and proof.get('source') in FAILED_SOURCES:
        raise ValueError('Known failing candidate: video open caused SError during DOS initialization; '
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


def require_watchdog():
    """WATCHDOG_SYSFS is disabled; PID 1 must own the hardware watchdog."""
    timeout = run('systemctl', 'show', '--property=RuntimeWatchdogUSec', '--value').strip()
    if timeout != '30s' or '1' not in run('fuser', '/dev/watchdog0').split():
        raise ValueError('PID 1 must hold the hardware watchdog with a 30s timeout')


def require_once(args):
    baseline = json.loads(Path(args.once_baseline).read_text())
    expected = {'/boot/edge/Image', '/boot/edge/vim4.dtb', '/boot/extlinux/extlinux.conf',
                '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json'}
    if set(baseline['files']) != expected:
        raise ValueError('Incomplete baseline file proof')
    for name, digest in baseline['files'].items():
        if sha(name) != digest:
            raise ValueError('Protected baseline changed: ' + name)
    if args.build_id in baseline['buildIds'] or os.uname().release != BASE_RELEASE:
        raise ValueError('Not the experimental one-time kernel')
    trial = '/var/lib/vim4-kvm/display-m1/' + args.build_id
    if 'init=' + trial + '/init' not in Path('/proc/cmdline').read_text().split():
        raise ValueError('Candidate was not selected through the private PID 1')
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    private = trial + '/modules/' + BASE_RELEASE
    # Ubuntu merges /lib into /usr/lib; mountinfo records the resolved target.
    target = str(Path('/lib/modules', BASE_RELEASE).resolve())
    if not any(line.split()[3:5] == [private, target]
               and 'ro' in line.split()[5].split(',') for line in mounts):
        raise ValueError('Private read-only candidate modules are not mounted')
    if (Path('/proc/sys/kernel/panic').read_text().strip() != '20' or
            Path('/proc/sys/kernel/panic_on_oops').read_text().strip() != '1'):
        raise ValueError('Candidate requires panic=20 and panic_on_oops=1')
    require_watchdog()


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
        require_candidate(args.action, proof)
        if proof['kernel_build_id'] != args.build_id:
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


def begin_stage(args, path=Path('/tmp/vim4-vdec-stages.json')):
    """A failed/interrupted stage blocks further experiments in this boot."""
    identity = {'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'build': args.build_id}
    state = json.loads(path.read_text()) if path.exists() else {}
    if state.get('identity') != identity:
        state = {'identity': identity, 'passed': []}
    previous = {'power': 'probe', 'mdec': 'power', 'compliance': 'mdec',
                'h264': 'compliance', 'h264-1080p': 'h264', 'wave': 'h264'}
    if state.get('pending') or state.get('failed'):
        raise ValueError('Previous stage did not finish; collect evidence and restore baseline')
    if args.action in previous and previous[args.action] not in state['passed']:
        raise ValueError('Required previous stage: ' + previous[args.action])
    if args.action in state['passed']:
        raise ValueError('Stage already completed; do not repeat hardware experiments')
    state['pending'] = args.action
    path.write_text(json.dumps(state) + '\n')
    return state


def finish_stage(state, success, path=Path('/tmp/vim4-vdec-stages.json')):
    action = state.pop('pending')
    if success:
        state['passed'].append(action)
    else:
        state['failed'] = action
    path.write_text(json.dumps(state) + '\n')


def t7_device():
    devices = list(Path('/sys/bus/platform/devices').glob('*/faulted'))
    if len(devices) != 1:
        raise ValueError('Expected one T7 VDEC diagnostic device')
    return devices[0].parent


def require_suspended(device):
    status = (device / 'power/runtime_status').read_text().strip()
    print('RUNTIME_AFTER_CLOSE', device.name, status, flush=True)
    if status != 'suspended':
        raise RuntimeError('Runtime PM did not suspend')


POWER_PARAM = '/sys/module/aml_vdec_drv/parameters/allow_t7_power'


def set_power_permission(enabled):
    # A subprocess bounds a sysfs write which might block inside the kernel.
    run('python3', '-c', 'from pathlib import Path; '
        f'Path({POWER_PARAM!r}).write_text({"Y" if enabled else "N"!r})', timeout=8)


def probe_without_power():
    if Path(POWER_PARAM).read_text().strip() != 'N':
        raise ValueError('Power opt-in must default off')
    run('udevadm', 'settle', '--timeout=5', timeout=8)
    # Reproduce the previously fatal userspace operation while the gate is off.
    run('python3', '-c', '''import errno, os, sys
try:
    fd = os.open(sys.argv[1], os.O_RDWR | os.O_NONBLOCK)
except OSError as error:
    if error.errno != errno.EPERM:
        raise
    print('OPEN_BLOCKED_EPERM')
else:
    os.close(fd)
    raise RuntimeError('Open unexpectedly bypassed power gate')
''', video_node('h264'), timeout=8)
    device = t7_device()
    print('PRE_POWER_STATE', (device / 'power_state').read_text().strip(), flush=True)
    if not (device / 'power_test').read_text().startswith('passed=0 '):
        raise ValueError('Probe unexpectedly performed a power test')
    require_suspended(device)
    print('PROBE_NO_DOS_MMIO; power gate off', flush=True)


def power_cycle():
    """Only one DOS read; this does not open video or run the decoder."""
    device = t7_device()
    run('udevadm', 'settle', '--timeout=5', timeout=8)
    print('PRE_POWER_STATE', (device / 'power_state').read_text().strip(), flush=True)
    set_power_permission(True)
    run('python3', '-c', 'from pathlib import Path; '
        f'Path({str(device / "power_test")!r}).write_text("1")', timeout=8)
    result = (device / 'power_test').read_text().strip()
    print('POWER_TEST', result, flush=True)
    if not result.startswith('passed=1 '):
        raise RuntimeError('Power test did not pass')
    state = (device / 'power_state').read_text().strip()
    print('POST_POWER_STATE', state, flush=True)
    if not state.startswith('VDEC[4]=1 '):
        raise RuntimeError('Secure VDEC domain did not power off')
    require_suspended(device)
    set_power_permission(False)


def mdec_cycle():
    """Complete prerequisites, read PIC_DC once, verify power-off; no video open."""
    power_cycle()
    device = t7_device()
    set_power_permission(True)
    run('python3', '-c', 'from pathlib import Path; '
        f'Path({str(device / "mdec_test")!r}).write_text("1")', timeout=8)
    result = (device / 'mdec_test').read_text().strip()
    print('MDEC_TEST', result, flush=True)
    if not result.startswith('passed=1 '):
        raise RuntimeError('MDEC single-read test did not pass')
    state = (device / 'power_state').read_text().strip()
    print('POST_MDEC_STATE', state, flush=True)
    if not state.startswith('VDEC[4]=1 '):
        raise RuntimeError('Secure VDEC domain did not power off after MDEC test')
    require_suspended(device)
    set_power_permission(False)


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
    if getattr(args, 'once_baseline', None):
        require_once(args)
    else:
        require_baseline_files()
    print('CANDIDATE_RUNNING', args.build_id, args.action, flush=True)
    full_hd = args.action == 'h264-1080p'
    width, height = (1920, 1080) if full_hd else (320, 256)
    stem = '1080p' if full_hd else 'small'
    clip = Path(args.fixtures) / (stem + '.h264')
    reference = Path(args.fixtures) / (stem + '.i420')
    if args.action in ('h264', 'h264-1080p', 'wave'):
        info = json.loads(run('ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                              '-of', 'json', str(clip)))['streams'][0]
        if (info['codec_name'], info['width'], info['height'], info['pix_fmt'],
                info['nb_read_frames']) != ('h264', width, height, 'yuv420p', '6'):
            raise ValueError('Expected the six-frame single-instance 8-bit fixture')
        hashes = json.loads((Path(args.fixtures) / 'fixtures.json').read_text())
        for name in (clip.name, reference.name):
            if hashlib.sha256((Path(args.fixtures) / name).read_bytes()).hexdigest() != hashes[name]:
                raise ValueError('Fixture hash mismatch: ' + name)
        factory = 'v4l2h264dec' if args.action == 'wave' else 'v4l2slh264dec'
        # The stateless factory appears only after its media device is registered.
        run('gst-inspect-1.0', 'videoconvert')
    stage = begin_stage(args)
    service_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'one-kvm']).returncode == 0
    loaded = {name for name in ('wave5', 't7_jpeg') if Path('/sys/module', name).exists()}
    critical = False
    removed = []
    candidate = None
    success = False
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
            probe_without_power()
            if faulted():
                raise RuntimeError('Fault reported at probe')
        elif args.action == 'power':
            power_cycle()
        elif args.action == 'mdec':
            mdec_cycle()
        elif args.action == 'compliance':
            mdec_cycle()
            set_power_permission(True)
            run('v4l2-compliance', '-d', video_node('h264'), timeout=20)
            require_suspended(t7_device())
        else:
            if args.action in ('h264', 'h264-1080p'):
                mdec_cycle()
                set_power_permission(True)
            video_node('wave' if args.action == 'wave' else 'h264')
            output = Path('/tmp/vim4-vdec-' + args.action + '.i420')
            factory = 'v4l2h264dec' if args.action == 'wave' else 'v4l2slh264dec'
            run('gst-inspect-1.0', factory, timeout=8)
            started = time.monotonic()
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            run('gst-launch-1.0', '-q', 'filesrc', 'location=' + str(clip), '!',
                'h264parse', '!', factory, '!', 'videoconvert', '!',
                f'video/x-raw,format=I420,width={width},height={height}', '!',
                'filesink', 'location=' + str(output), timeout=15 if full_hd else 10)
            elapsed = time.monotonic() - started
            finished = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = finished.ru_utime + finished.ru_stime - usage.ru_utime - usage.ru_stime
            if output.read_bytes() != reference.read_bytes():
                raise ValueError('Decoded frames differ from software reference')
            print('EXACT_FRAMES_MATCH', hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)
            frame_size = width * height * 3 // 2
            frames = output.read_bytes()
            if len(frames) != frame_size * 6:
                raise ValueError('Expected exactly six complete I420 frames')
            for index in range(6):
                digest = hashlib.md5(frames[index * frame_size:(index + 1) * frame_size]).hexdigest()
                print('FRAME_MD5', index, digest, flush=True)
            print('SHORT_CLIP_SECONDS', elapsed, 'including pipeline startup', flush=True)
            print('SHORT_CLIP_CPU_SECONDS', cpu, 'ONE_CORE_PERCENT', 100 * cpu / elapsed,
                  'FRAMES_PER_SECOND', 6 / elapsed, flush=True)
            if args.action in ('h264', 'h264-1080p'):
                require_suspended(t7_device())
        if faulted():
            raise RuntimeError('DMA stop not confirmed')
        success = True
    except subprocess.TimeoutExpired:
        critical = True
        raise
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError):
        critical = critical or faulted() or candidate is not None
        raise
    finally:
        if critical or faulted():
            finish_stage(stage, False)
            Path('/tmp/vim4-vdec-reset-required').write_text('Do not reload codecs. Restore boot baseline and reset.\n')
            print('RESET_REQUIRED: retain DMA; no unload/reload or automatic retry', flush=True)
        else:
            try:
                if candidate and Path('/sys/module', candidate).exists():
                    if candidate == 'aml_vdec_drv':
                        set_power_permission(False)
                    run('modprobe', '-r', candidate)
                for name in sorted(loaded.intersection(removed)):
                    run('modprobe', name)
                if service_active:
                    run('systemctl', 'start', 'one-kvm')
                finish_stage(stage, success)
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
    parser.add_argument('--payload', default='/var/tmp/vim4-vdec-mdec')
    parser.add_argument('--backup', default='/var/backups/vim4-vdec-mdec-20261022')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--at-board', action='store_true')
    parser.add_argument('--once-baseline', help='Board JSON proof for watchdog-protected RAM boot')
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
                          'order': ['heavy then board locks', 'RAM-only boot or supervised baseline recovery',
                                    'probe: gate off, EPERM, read-only SMC status',
                                    'power: explicit opt-in, one DOS read, verified power off',
                                    'mdec: secure policy + verified prerequisites, one PIC_DC read, power off',
                                    'compliance only after probe + power + mdec receipts',
                                    'stop clients', 'exclusive codec lease', args.action,
                                    'safe unload or RESET_REQUIRED', 'restore boot baseline',
                                    'encoding + HDMI + services + UDC + actual HID verification']}, indent=2))
        return
    if not (args.at_board or args.once_baseline) or args.manifest is None:
        parser.error('--execute requires --at-board or --once-baseline, and --manifest')
    proof = json.loads(args.manifest.read_text())
    require_candidate(args.action, proof, once=bool(args.once_baseline))
    if not args.locked:
        command = ['/usr/bin/lockf', '-t', '3600', '/tmp/vim4-heavy.lock',
                   '/usr/bin/lockf', '-t', '600', '/tmp/vim4-board.lock',
                   sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--locked']
        subprocess.run(command, check=True)
        return
    source = Path(__file__).read_text()
    remote = ['sudo', 'python3', '-', args.action, '--remote',
              '--build-id', proof['kernel_build_id'], '--fixtures', args.fixtures,
              '--payload', args.payload, '--backup', args.backup]
    if args.once_baseline:
        remote.extend(['--once-baseline', args.once_baseline])
    subprocess.run(['ssh', '-o', 'ConnectTimeout=8', 'vim4', shlex.join(remote)],
                   input=source, text=True, check=True, timeout=180)


if __name__ == '__main__':
    main()
