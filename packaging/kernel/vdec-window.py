#!/usr/bin/env python3
"""Prepare or run one supervised decoder window; default is offline plan only.

Run on Mac. --execute requires --at-board or --once-baseline and a matched manifest.
The latter uses a watchdog-protected RAM boot and never writes default boot files.
Boot actions install the candidate and arm baseline recovery. Reboots and
functional baseline checks are supervised steps described in the bringup record.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import threading
import time


BOOT_ACTIONS = ('boot-install', 'arm-baseline', 'verify-baseline')
ACTIONS = (*BOOT_ACTIONS, 'probe', 'power', 'snapshot', 'mdec', 'compliance', 'fluster',
           'performance', 'h264', 'h264-1080p', 'wave')
BASE_ID = 'f283ab1f8a001a19bab5247afc4f9b0c00c1da99'
BASE_RELEASE = '7.3.0-vim4kvm-uhd1+'
BOOT_DIR = Path('/boot/kernels') / BASE_RELEASE
BASE_FILES = {
    'Image': '855f0fa8caa49fdb9973bd7cd1cbbfaa2c5f62138574862e651e16eb0fda42b5',
    'vim4.dtb': 'd2333e962326d0710300b71e758440a94b177eb273921f70e5ba12eb5f640cf6',
}
FAILED_SOURCES = {
    '5bf7d6359df9ff68d8746851cf45de40611988a1',
    '34ab72b7fbecaa13347aca58584b4bcb10b1b73e',
    'e8ebc2e82734739a7ae0f1a91117cebc36ff7b89',
    'c6fc96a347d0929a9385c09b408c333a50834091',
    'a915603f5efb795afc72b5d92aa2c72e0e939a14',
}
REGISTER_STEPS = (
    'CPU APB + DOS clocks + NIC3 on; require VDEC off',
    'DOS_GCLK_EN0 read (VDEC off)',
    'DOS_GCLK_EN0 write (preserve HCODEC)',
    'DOS_GCLK_EN0 verify',
    '800MHz + VDEC on + secure policy; verify domains and physical CLKCTRL',
    'DOS_GCLK_EN0 verify after secure power-on',
    'DOS_SW_RESET0 read',
    'DOS_MEM_PD_VDEC read',
    'GCLK_EN first read',
    'GCLK_EN write',
    'GCLK_EN verify',
    'MDEC_PIC_DC_CTRL single read',
    'clocks + VDEC off; release NIC3; verify off',
)


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
        raise ValueError('Known failing candidate: SError during DOS/MDEC initialization; '
                         'prepare a revised offline candidate before another board window')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_result(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def terminate_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def bounded_process(command, log, timeout, env=None):
    """Bound the entire Fluster process tree, including its decoder children."""
    with log.open('w') as stream:
        stream.write(shlex.join(command) + '\n')
        stream.flush()
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            # Killing Fluster alone leaves Pool/GStreamer children holding the
            # video device. Hardware DMA safety still requires baseline recovery.
            terminate_process_group(process)
            raise


def fluster_result(path, suite, decoder, vector):
    """Exit zero without a selected vector result is not conformance evidence."""
    try:
        data = json.loads(path.read_text())
        entry = data['test_suites'][suite]['decoders'][decoder]['vectors'][vector]
        status = entry['result']
        elapsed = float(entry['time'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError('Missing or malformed Fluster result for ' + vector) from error
    if status not in ('Success', 'Fail', 'Timeout', 'Error', 'Not run', 'Not supported'):
        raise ValueError('Unexpected Fluster result: ' + str(status))
    return {'result': status, 'time': elapsed}


def verify_files(root, files):
    for name, expected in files.items():
        path = root / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            raise ValueError('Invalid manifest file: ' + name)
        if sha(path) != expected:
            raise ValueError('Manifest checksum differs: ' + name)


def run_fluster(plan, output, deadline, env):
    bundle = Path(plan['bundle'])
    manifest_path = bundle / 'bundle-manifest.json'
    if sha(manifest_path) != plan['bundle_sha256']:
        raise ValueError('Fluster bundle manifest differs from host preparation')
    manifest = json.loads(manifest_path.read_text())
    suite = next(s for s in manifest['suites'] if s['name'] == plan['suite'])
    decoder = suite[plan['kernel'] + '_decoder']
    start, count = plan['start'], plan['count']
    timeout = plan['vector_timeout_seconds']
    if not (0 <= start < len(suite['vectors']) and 0 < count <= len(suite['vectors']) - start
            and 1 <= timeout <= 120):
        raise ValueError('Invalid Fluster vector range or timeout')
    selected = suite['vectors'][start:start + count]
    inputs = {v['input_path'] for v in selected if 'input_path' in v}
    verify_files(bundle, {name: digest for name, digest in manifest['files'].items()
                          if not name.startswith('resources/') or name in inputs})
    report = {'suite': suite['name'], 'decoder': decoder,
              'bundle_sha256': plan['bundle_sha256'], 'fluster_revision': manifest['fluster_revision'],
              'vectors': {v['name']: {'result': 'Not run', 'reason': v.get('reason', 'outside this window')}
                          for v in suite['vectors']}}
    for vector in selected:
        report['vectors'][vector['name']]['reason'] = vector.get('reason', 'not reached')
    result_path = output / 'results.json'

    def save():
        statuses = [v['result'] for v in report['vectors'].values()]
        report['counts'] = {status: statuses.count(status) for status in sorted(set(statuses))}
        report['total'] = len(statuses)
        save_result(result_path, report)

    save()
    if any(v.get('availability', 'available') != 'available' for v in selected):
        report['stopped'] = 'selected window contains unavailable inputs; no decoder was started'
        save()
        raise ValueError(report['stopped'])
    base = [sys.executable, str(bundle / 'fluster/fluster.py'), '-ne',
            '-tsd', str(bundle / 'suites'), '-r', str(bundle / 'resources')]
    try:
        listing = output / 'fluster-list.log'
        code = bounded_process([*base, 'list', '-c', '-d', suite['codec']], listing,
                               min(45, max(1, deadline - time.monotonic())), env)
        available = listing.read_text()
        for name in [decoder, *([suite['reference_decoder']] if 'reference_decoder' in suite else [])]:
            if code or not re.search(r'^\s*' + re.escape(name) + r':.*\.\.\. OK\s*$', available, re.M):
                raise ValueError('Fluster decoder unavailable: ' + name)
        for index, vector in enumerate(selected, start):
            # A pixel comparison may decode twice (hardware and ISO reference).
            process_limit = timeout * (2 if suite['test_method'] == 'pixel' else 1) + 15
            if time.monotonic() + process_limit > deadline:
                report['stopped'] = 'window budget reserved for recovery'
                save()
                raise TimeoutError(report['stopped'])
            name = vector['name']
            raw = output / f'vector-{index:04d}.json'
            log = output / f'vector-{index:04d}.log'
            command = [*base, '-o', str(output / f'decode-{index:04d}'), 'run',
                       '-j', '1', '-t', str(timeout), '-ff', '-ts', suite['name'],
                       '-tv', name, '-d', decoder, '-s', '-so', str(raw), '-f', 'json']
            try:
                code = bounded_process(command, log, process_limit, env)
                entry = fluster_result(raw, suite['name'], decoder, name)
                if code and entry['result'] == 'Success':
                    entry = {'result': 'Error', 'reason': f'Fluster exited {code} despite Success'}
            except subprocess.TimeoutExpired:
                entry = {'result': 'Timeout', 'reason': 'whole process tree deadline'}
            except (OSError, ValueError) as error:
                entry = {'result': 'Error', 'reason': str(error)}
            report['vectors'][name] = dict(entry, raw_result=raw.name, log=log.name)
            save()
            if entry['result'] != 'Success':
                raise RuntimeError('First Fluster failure: ' + name + ': ' + entry['result'])
            if plan['kernel'] == 'mainline' and faulted():
                raise RuntimeError('DMA stop not confirmed after ' + name)
    except BaseException as error:
        report['stopped'] = str(error)
        save()
        raise


def validate_acceptance_plan(plan, proof):
    if proof.get('source') in FAILED_SOURCES:
        raise ValueError('Known failing candidate')
    if plan['kernel'] not in ('mainline', 'vendor'):
        raise ValueError('Expected mainline or vendor comparison')
    prefix = '7.3.' if plan['kernel'] == 'mainline' else '5.15.'
    if not proof['release'].startswith(prefix) or not proof.get('kernel_build_id'):
        raise ValueError('Kernel manifest does not match the comparison side')
    if not 0 < plan['window_seconds'] <= 1800 or plan['recovery_seconds'] < 180:
        raise ValueError('Window must leave at least three minutes for recovery and be <=30 minutes')
    if plan['window_seconds'] <= plan['recovery_seconds'] + 60:
        raise ValueError('Insufficient test budget')
    if not re.fullmatch(r'[\w.-]+', plan['board_window']) or not plan['video_check']:
        raise ValueError('Existing board-window recovery proof and video check are required')


def require_acceptance_kernel(plan, proof):
    if os.geteuid() or os.uname().release != proof['release']:
        raise ValueError('Expected root on the manifested kernel')
    if build_id('/sys/kernel/notes') != proof['kernel_build_id']:
        raise ValueError('Running kernel build ID differs')
    require_watchdog()
    if Path('/tmp/vim4-vdec-reset-required').exists():
        raise ValueError('Prior failure requires baseline recovery before another action')
    for name, expected in plan['protected_files'].items():
        if sha(name) != expected:
            raise ValueError('Protected baseline changed: ' + name)
    if not plan['protected_files']:
        raise ValueError('Protected baseline files are required')
    governors = list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_governor'))
    if not governors:
        raise ValueError('CPU policy cannot be verified')
    for path in governors:
        if path.read_text().strip() != 'performance':
            raise ValueError('Decoder comparisons require the unchanged performance CPU policy')
    for path in Path('/sys/kernel/config/usb_gadget').glob('*/functions/mass_storage.*/lun.*/file'):
        if path.read_text().strip():
            raise ValueError('Virtual media must be ejected before the recovery reboot')
    for name, expected in plan['files'].items():
        if sha(name) != expected:
            raise ValueError('Validation tool/input differs: ' + name)
    if plan['kernel'] == 'mainline':
        trial = plan['trial_root'].rstrip('/')
        if not trial.startswith('/var/lib/vim4-kvm/ram-candidates/'):
            raise ValueError('Expected a private RAM candidate')
        if 'init=' + trial + '/init' not in Path('/proc/cmdline').read_text().split():
            raise ValueError('Not booted through the manifested private PID 1')
        private = trial + '/modules/' + proof['release']
        target = str(Path('/lib/modules', proof['release']).resolve())
        if not any(line.split()[3:5] == [private, target] and 'ro' in line.split()[5].split(',')
                   for line in Path('/proc/self/mountinfo').read_text().splitlines()):
            raise ValueError('Private candidate modules are not mounted read-only')
        if (Path('/proc/sys/kernel/panic').read_text().strip() != '20' or
                Path('/proc/sys/kernel/panic_on_oops').read_text().strip() != '1'):
            raise ValueError('Candidate requires panic=20 and panic_on_oops=1')
    if plan.get('debug_kernel'):
        config = gzip.decompress(Path('/proc/config.gz').read_bytes())
        if hashlib.sha256(config).hexdigest() != proof['config_sha256']:
            raise ValueError('Running debug configuration differs from manifest')
        for name in ('KASAN', 'KASAN_GENERIC', 'DEBUG_KMEMLEAK', 'PROVE_LOCKING',
                     'DEBUG_ATOMIC_SLEEP', 'DMA_API_DEBUG'):
            if ('CONFIG_' + name + '=y').encode() not in config.splitlines():
                raise ValueError('Missing debug check: ' + name)


def prepare_acceptance_decoder(plan, proof):
    coexistence = plan.get('coexistence', False)
    if coexistence:
        require_services()
    else:
        run('systemctl', 'stop', 'one-kvm', timeout=20)
        for path in Path('/proc').glob('[0-9]*/fd/*'):
            try:
                target = str(path.readlink())
            except OSError:
                continue
            if target.startswith(('/dev/video', '/dev/jpegenc')):
                raise ValueError('A video client still owns a device: ' + str(path))
    if plan['kernel'] == 'vendor':
        return
    if coexistence and Path('/sys/module/aml_vdec_drv').exists():
        raise ValueError('Coexistence starts from a fresh decoder instance')
    for name in (() if coexistence else ('aml_vdec_drv', 'wave5', 't7_jpeg')):
        if Path('/sys/module', name).exists():
            run('modprobe', '-r', name, timeout=10)
    private = plan.get('private_driver')
    if private:
        module = Path(private['path'])
        if (private['image_build_id'] != proof['kernel_build_id'] or
                private['base_revision'] != proof['source'] or
                sha(module) != plan['files'][str(module)] or
                sha(private['patch']) != plan['files'][private['patch']] or
                run('modinfo', '-F', 'vermagic', str(module)).strip() != private['vermagic'] or
                private['vermagic'].split()[0] != proof['release']):
            raise ValueError('Private module must match the exact Image and recorded source patch')
        for dependency in run('modinfo', '-F', 'depends', str(module)).strip().split(','):
            if dependency:
                run('modprobe', dependency)
        run('insmod', str(module), 'enable_t7=1', 't7_snapshot_only=0', timeout=10)
        if build_id('/sys/module/aml_vdec_drv/notes/.note.gnu.build-id') != private['build_id']:
            raise ValueError('Loaded private decoder build ID differs')
    else:
        module = Path(run('modinfo', '-n', 'aml_vdec_drv').strip())
        relative = str(module.resolve().relative_to((Path('/lib/modules') / proof['release']).resolve()))
        if sha(module) != proof['modules'][relative]:
            raise ValueError('Decoder module differs from the full kernel package')
        run('modprobe', 'aml_vdec_drv', 'enable_t7=1', 't7_snapshot_only=0', timeout=10)
    probe_without_power()
    mdec_cycle()
    if plan.get('hevc'):
        hevc_cycle()
        set_power_permission(True)
        run('python3', '-c', 'from pathlib import Path; '
            f'Path({str(t7_device() / "hevc_core_test")!r}).write_text("1")', timeout=8)
        if not (t7_device() / 'hevc_core_test').read_text().startswith('passed=1 '):
            raise RuntimeError('HEVC firmware preflight failed')
    set_power_permission(True)


def run_compliance(plan, output, deadline, env):
    tool = plan['compliance_tool']
    if bounded_process([tool, '--version'], output / 'v4l-utils-version.log', 10, env):
        raise RuntimeError('Unable to record v4l-utils version')
    results = []
    for item in plan['nodes']:
        matching = [p.parent.name for p in Path('/sys/class/video4linux').glob('video*/name')
                    if p.read_text().strip() == item['name']]
        if len(matching) != 1:
            raise ValueError('Expected exactly one decoder node: ' + item['name'])
        if item.get('fourcc'):
            setup = [plan['control_tool'], '-d', '/dev/' + matching[0],
                     '--set-fmt-video-out', f"width={item['width']},height={item['height']},pixelformat={item['fourcc']}"]
            if bounded_process(setup, output / (item['id'] + '-format.log'), 10, env):
                raise RuntimeError('Unable to set compliance input format: ' + item['id'])
        command = [tool, '-E', '-W', '-d', '/dev/' + matching[0], '-s', str(item['frames'])]
        if item.get('media'):
            media = item['media']
            if media == 'auto':
                device = (Path('/sys/class/video4linux') / matching[0] / 'device').resolve()
                related = [p for p in Path('/sys/bus/media/devices').glob('media*')
                           if p.resolve().parent == device]
                if len(related) != 1:
                    raise ValueError('Expected one media device belonging to ' + matching[0])
                media = '/dev/' + related[0].name
            command.extend(['-m', media])
        if item.get('stream'):
            command.extend(['--stream-from-hdr', item['fourcc'] + '=' + item['stream']])
        timeout = min(120, deadline - time.monotonic())
        if timeout < 30:
            raise TimeoutError('Insufficient time for streaming compliance and recovery')
        log = output / (item['id'] + '-compliance.log')
        code = bounded_process(command, log, timeout, env)
        content = log.read_text()
        summaries = re.findall(r'Total for[^\n]*:.*?Succeeded:\s*(\d+),\s*Failed:\s*(\d+),\s*Warnings:\s*(\d+)', content)
        passed = bool(summaries) and not code and all(int(failed) == int(warnings) == 0
                                                     for _, failed, warnings in summaries)
        results.append(dict(id=item['id'], node=item['name'], exit=code, summaries=summaries, passed=passed,
                            stateless_streaming='not covered by compliance; requires Fluster'
                            if item.get('media') else None))
        save_result(output / 'results.json', results)
        if not passed:
            raise RuntimeError('Streaming compliance failed: ' + item['name'])


def run_performance(plan, output, deadline, env):
    case = plan['performance']
    seconds = case['seconds']
    if not 1 <= seconds <= 600 or (case['sync'] and seconds != 600):
        raise ValueError('Playback requires a full 600 seconds; throughput must be bounded')
    if not case.get('motion') or case['clip'] not in plan['files']:
        raise ValueError('Performance requires a SHA-locked motion clip')
    if not plan['clock_files']:
        raise ValueError('Explicit reviewed decoder clock/DVFS files are required')
    if time.monotonic() + seconds + 30 > deadline:
        raise TimeoutError('Insufficient performance and recovery budget')
    stop = threading.Event()

    def telemetry():
        paths = [Path(name) for name in plan['clock_files']]
        paths += list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'))
        paths += [Path('/proc/stat')]
        with (output / 'clocks-cpu.jsonl').open('w') as log:
            while not stop.is_set():
                sample = {'wall_ns': time.time_ns(), 'monotonic_ns': time.monotonic_ns(),
                          'values': {}, 'errors': {}}
                for path in paths:
                    try:
                        sample['values'][str(path)] = path.read_text().strip()
                    except OSError as error:
                        sample['errors'][str(path)] = str(error)
                log.write(json.dumps(sample) + '\n')
                log.flush()
                stop.wait(1)

    monitor = threading.Thread(target=telemetry, daemon=True)
    monitor.start()
    log = output / 'performance.log'
    try:
        code = bounded_process([plan['benchmark_tool'], case['pipeline'], str(seconds),
                                '1' if case['sync'] else '0'], log, seconds + 30, env)
    finally:
        stop.set()
        monitor.join(timeout=5)
    summaries = [json.loads(line) for line in log.read_text().splitlines()
                 if line.startswith('{"event":"summary"')]
    report = {'case': case, 'clip_sha256': plan['files'][case['clip']],
              'coexistence': bool(plan.get('coexistence')), 'exit': code, 'summaries': summaries}
    save_result(output / 'results.json', report)
    if code or len(summaries) != 1 or not summaries[0]['success']:
        raise RuntimeError('Decoder performance window did not complete')
    samples = [json.loads(line) for line in (output / 'clocks-cpu.jsonl').read_text().splitlines()]
    if monitor.is_alive() or not samples or any(s['errors'] for s in samples):
        raise RuntimeError('Clock/CPU telemetry is incomplete; inspect raw errors')


def require_clean_kernel_log(output):
    kernel_log = run('journalctl', '-k', '-b', '--no-pager', timeout=15)
    (output / 'kernel.log').write_text(kernel_log)
    # DMA-API also emits normal "debugging enabled" startup messages. Actual
    # DMA violations emit WARNING, as the ADLA failure in debug run32 did.
    if re.search(r'BUG:|Oops:|WARNING:|Call trace:|possible circular locking|KASAN:', kernel_log):
        raise RuntimeError('Kernel diagnostic failure; inspect raw kernel log')


def acceptance_window(args):
    plan = json.loads(args.validation_plan.read_text())
    proof = json.loads(args.manifest.read_text())
    validate_acceptance_plan(plan, proof)
    require_acceptance_kernel(plan, proof)
    output = Path(plan['output'])
    output.mkdir(parents=True, exist_ok=False)
    seconds = args.validation_seconds
    if seconds is None or not 60 <= seconds <= plan['window_seconds'] - plan['recovery_seconds']:
        raise ValueError('Host must provide the remaining validation budget')
    # Leave time inside the remote process limit for kmemleak and journal output.
    deadline = time.monotonic() + seconds - 45
    env = dict(os.environ)
    env.update(plan.get('environment', {}))
    env['GST_REGISTRY'] = str(output / 'gst-registry.bin')
    # Changes in kernel diagnostics are captured even when the decoder process
    # fails. No unload/reload after failure: the caller must restore the baseline.
    success = False
    try:
        require_clean_kernel_log(output)
        prepare_acceptance_decoder(plan, proof)
        require_clean_kernel_log(output)
        if args.action == 'fluster':
            if plan.get('nodes'):
                compliance_output = output / 'compliance'
                compliance_output.mkdir()
                run_compliance(plan, compliance_output, deadline, env)
            run_fluster(plan, output, deadline, env)
        elif args.action == 'compliance':
            run_compliance(plan, output, deadline, env)
        elif args.action == 'performance':
            run_performance(plan, output, deadline, env)
        else:
            raise ValueError('Validation plan supports compliance, fluster or performance')
        if plan['kernel'] == 'mainline':
            if faulted():
                raise RuntimeError('Decoder reported an unsafe stop')
            require_suspended(t7_device())
        if plan.get('debug_kernel'):
            run('python3', '-c', 'from pathlib import Path; '
                'Path("/sys/kernel/debug/kmemleak").write_text("scan")', timeout=30)
            leaks = Path('/sys/kernel/debug/kmemleak').read_text()
            (output / 'kmemleak.log').write_text(leaks)
            if leaks.strip():
                raise RuntimeError('kmemleak reported outstanding objects')
        require_clean_kernel_log(output)
        success = True
    finally:
        if not (output / 'kernel.log').exists():
            try:
                bounded_process(['journalctl', '-k', '-b', '--no-pager'], output / 'kernel.log', 15)
            except (OSError, subprocess.SubprocessError):
                print('Kernel log collection failed; preserve UART evidence', flush=True)
        if not success:
            Path('/tmp/vim4-vdec-reset-required').write_text('Validation failed; recover baseline, no codec retry.\n')
        save_result(output / 'window-status.json', {'success': success, 'recovery_required': not success})
        print('VALIDATION_COMPLETE' if success else 'RESET_REQUIRED', str(output), flush=True)


def execute_acceptance(args, plan, proof):
    validate_acceptance_plan(plan, proof)
    repo = Path(__file__).resolve().parents[2]
    recovery = repo / 'logs' / plan['board_window']
    if not (recovery / 'baseline-proof.json').is_file():
        raise ValueError('Prepare the existing board-window baseline proof before this action')
    # A prepared batch may already own the queue ticket. Do not nest locks.
    from importlib.machinery import SourceFileLoader
    queue_module = SourceFileLoader('vdec_board_queue', str(repo / 'tools/board-queue')).load_module()
    queue = queue_module.Queue()
    ticket = os.environ.get('BOARD_TICKET')
    if not ticket:
        if args.locked:
            raise ValueError('--locked requires a live board ticket')
        subprocess.run([str(repo / 'tools/board-queue'), 'run', '--who', 'hwdecode-parity',
                        '--purpose', 'vdec-' + args.action, '--max-min', str(plan['window_seconds'] / 60),
                        '--', sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--locked'], check=True)
        return
    item = queue.read(ticket)
    remaining = item['started'] + item['seconds'] - time.time()
    if item['state'] != 'held' or item['heavy'] or remaining < plan['window_seconds'] - 30:
        raise ValueError('Board ticket lacks the complete validation and recovery budget')
    deadline = time.monotonic() + min(remaining, plan['window_seconds'])
    remote = Path(args.payload)
    local = recovery / ('validation-' + args.action + '-' + str(time.time_ns()))
    local.mkdir()
    shutil.copy2(args.manifest, local / 'kernel-manifest.json')
    shutil.copy2(args.validation_plan, local / 'validation-plan.json')
    save_result(local / 'runner.json', {'source_sha256': sha(Path(__file__))})
    observer = None
    observer_log = None
    sampling = args.action == 'performance'
    try:
        subprocess.run(['ssh', '-oBatchMode=yes', 'vim4', shlex.join(['mkdir', '-p', str(remote)])], check=True, timeout=15)
        for path, name in ((args.manifest, 'kernel-manifest.json'),
                           (args.validation_plan, 'validation-plan.json'), (Path(__file__), 'vdec-window.py')):
            subprocess.run(['scp', str(path), 'vim4:' + str(remote / name)], check=True, timeout=30)
        # Upload and collection consume the same lease as decoding. A remote
        # timeout also terminates descendants if the SSH connection disappears.
        seconds = int(deadline - time.monotonic() - plan['recovery_seconds'] - 45)
        if seconds < 60:
            raise TimeoutError('Preparation exhausted the validation budget')
        command = ['sudo', '-n', 'timeout', '--signal=TERM', '--kill-after=5', str(seconds),
                   'python3', str(remote / 'vdec-window.py'), args.action, '--remote',
                   '--validation-seconds', str(seconds),
                   '--validation-plan', str(remote / 'validation-plan.json'),
                   '--manifest', str(remote / 'kernel-manifest.json')]
        if sampling:
            queue.sampling(ticket, True)
        if plan.get('coexistence'):
            if not sampling or not plan.get('kvm_check'):
                raise ValueError('Coexistence requires performance and a concurrent video receiver')
            observer_log = (local / 'kvm-receiver.json').open('w')
            observer = subprocess.Popen(plan['kvm_check'], stdout=observer_log,
                                        start_new_session=True)
        with (local / 'window.log').open('w') as log:
            subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', 'vim4', shlex.join(command)],
                           stdout=log, stderr=subprocess.STDOUT, check=True,
                           timeout=seconds + 10)
        if observer:
            if observer.wait(timeout=30):
                raise RuntimeError('Concurrent KVM receiver failed')
            observer_log.flush()
            measured = json.loads((local / 'kvm-receiver.json').read_text())
            first, last = measured['samples'][0], measured['samples'][-1]
            if last['framesDecoded'] <= first['framesDecoded'] or measured['fps'] <= 0:
                raise RuntimeError('Concurrent KVM did not advance decoded frames')
            save_result(local / 'kvm-summary.json', {'fps': measured['fps'],
                'frames_decoded': last['framesDecoded'] - first['framesDecoded'],
                'frames_dropped': last['framesDropped'] - first['framesDropped'],
                'freezes': last['freezeCount'] - first['freezeCount'],
                'first_timestamp_ms': first['timestamp'], 'last_timestamp_ms': last['timestamp']})
    finally:
        try:
            if observer and observer.poll() is None:
                terminate_process_group(observer)
            if observer_log:
                observer_log.close()
            if sampling:
                queue.sampling(ticket, False)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            (local / 'observer-cleanup-error.txt').write_text(str(error) + '\n')
        try:
            command = ['sudo', '-n', 'tar', '-C', plan['output'], '--exclude=gst-registry.bin', '-cf', '-', '.']
            with (local / 'results.tar').open('wb') as archive:
                subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=5', 'vim4', shlex.join(command)],
                               stdout=archive, check=True, timeout=30)
            with tarfile.open(local / 'results.tar') as archive:
                archive.extractall(local / 'results', filter='data')
        except (OSError, subprocess.SubprocessError, tarfile.TarError) as error:
            (local / 'collection-error.txt').write_text(str(error) + '\n')
        remaining = deadline - time.monotonic()
        if remaining < plan['recovery_seconds']:
            save_result(local / 'recovery-handoff.json', {
                'board_window': plan['board_window'], 'remaining_seconds': remaining,
                'reason': 'insufficient recovery budget; no reboot initiated'})
            raise TimeoutError('Recovery budget exhausted; preserve proof for recovery handoff')
        subprocess.run([str(repo / 'tools/board-window'), '--window', plan['board_window'],
                        '--device', plan['serial_device'], 'return-baseline',
                        '--video-check', *plan['video_check']], check=True,
                       timeout=plan['recovery_seconds'])


def require_baseline_files():
    for name, expected in BASE_FILES.items():
        if sha(BOOT_DIR / name) != expected:
            raise ValueError('Baseline boot file mismatch: ' + name)


def require_watchdog():
    """WATCHDOG_SYSFS is disabled; PID 1 must own the hardware watchdog."""
    timeout = run('systemctl', 'show', '--property=RuntimeWatchdogUSec', '--value').strip()
    if timeout != '30s' or '1' not in run('fuser', '/dev/watchdog0').split():
        raise ValueError('PID 1 must hold the hardware watchdog with a 30s timeout')


def require_once(args):
    baseline = json.loads(Path(args.once_baseline).read_text())
    expected = {str(BOOT_DIR/'Image'), str(BOOT_DIR/'vim4.dtb'), '/boot/extlinux/extlinux.conf',
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
        if selected.get('LINUX') != ('/kernels/'+BASE_RELEASE+'/Image') or selected.get('FDT') != ('/kernels/'+BASE_RELEASE+'/vim4.dtb'):
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
        if (shutil.disk_usage('/boot').free + (BOOT_DIR/'Image').stat().st_size <
                (payload / 'Image').stat().st_size + 4_000_000):
            raise ValueError('Insufficient boot space for candidate replacement')
        # Refuse active virtual media before the reboot disconnects the host.
        for path in Path('/sys/kernel/config/usb_gadget').glob('*/functions/mass_storage.*/lun.*/file'):
            if path.read_text().strip():
                raise ValueError('Safely eject active virtual media before this window')
        backup.mkdir(mode=0o700)
        for name in BASE_FILES:
            shutil.copy2(BOOT_DIR / name, backup / name)
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
                target = BOOT_DIR / name
                target.unlink()
                shutil.copy2(payload / name, target)
            os.sync()
        except BaseException:
            for name in BASE_FILES:
                shutil.copy2(backup / name, BOOT_DIR / name)
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
            target = BOOT_DIR / name
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
    previous = {'power': 'probe', 'snapshot': 'power', 'mdec': 'power', 'compliance': 'mdec',
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
    """One DOS transaction per sysfs write; stop before any following step on error."""
    power_cycle()
    device = t7_device()
    set_power_permission(True)
    for step, description in enumerate(REGISTER_STEPS, 1):
        print('REGISTER_STEP_BEGIN', step, description, flush=True)
        run('python3', '-c', 'from pathlib import Path; '
            f'Path({str(device / "register_step")!r}).write_text({str(step)!r})', timeout=8)
        status = (device / 'register_step').read_text().strip()
        expected = step if step < len(REGISTER_STEPS) else 0
        if not status.startswith(f'step={expected} ') or not status.endswith(' failed=0'):
            raise RuntimeError('Register step failed: ' + status)
        print('REGISTER_STEP_COMPLETE', step, status, flush=True)
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


def hevc_cycle():
    """Probe HEVC power/clocks after MDEC validation, without firmware or DMA."""
    device = t7_device()
    require_suspended(device)
    if not (device / 'mdec_test').read_text().startswith('passed=1 '):
        raise RuntimeError('HEVC probe requires the completed MDEC power sequence')
    set_power_permission(True)
    run('python3', '-c', 'from pathlib import Path; '
        f'Path({str(device / "hevc_test")!r}).write_text("1")', timeout=8)
    result = (device / 'hevc_test').read_text().strip()
    print('HEVC_POWER_TEST', result, flush=True)
    if not result.startswith('passed=1 ') or faulted():
        raise RuntimeError('HEVC power-on/read/reference-release did not pass')
    require_suspended(device)
    set_power_permission(False)


def outer_register_snapshot(payload):
    """Stop at step eight; the reader independently denies all internal DOS addresses."""
    if Path('/sys/module/aml_vdec_drv/parameters/t7_snapshot_only').read_text().strip() != 'Y':
        raise ValueError('Snapshot requires the kernel-enforced eight-step limit')
    power_cycle()
    device = t7_device()
    set_power_permission(True)
    for step, description in enumerate(REGISTER_STEPS[:8], 1):
        print('REGISTER_STEP_BEGIN', step, description, flush=True)
        run('python3', '-c', 'from pathlib import Path; '
            f'Path({str(device / "register_step")!r}).write_text({str(step)!r})', timeout=8)
        status = (device / 'register_step').read_text().strip()
        if not status.startswith(f'step={step} ') or not status.endswith(' failed=0'):
            raise RuntimeError('Register step failed: ' + status)
        print('REGISTER_STEP_COMPLETE', step, status, flush=True)
    for name, path in (('clk', '/sys/kernel/debug/clk/clk_summary'),
                       ('genpd', '/sys/kernel/debug/pm_genpd/pm_genpd_summary')):
        try:
            value = Path(path).read_text()
        except OSError as error:
            value = str(error)
        (Path(payload) / f'active-{name}.txt').write_text(value)
        print('ACTIVE_STATE', name, value, flush=True)
    print('OUTER_SNAPSHOT_BEGIN', flush=True)
    subprocess.run([str(Path(payload) / 'register-reader'), '--devmem',
                    str(Path(payload) / 'addresses.txt')], check=True, timeout=20)
    print('OUTER_SNAPSHOT_COMPLETE', flush=True)
    # Zero never touches DOS and is valid even with the snapshot limit enabled.
    run('python3', '-c', 'from pathlib import Path; '
        f'Path({str(device / "register_step")!r}).write_text("0")', timeout=8)
    state = (device / 'power_state').read_text().strip()
    if not state.startswith('VDEC[4]=1 '):
        raise RuntimeError('Snapshot abort did not power off VDEC')
    print('POST_SNAPSHOT_STATE', state, flush=True)
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
    width, height, frame_count = ((1920, 1080, 6) if full_hd else
                                  (320, 256, 6) if args.action == 'wave' else
                                  (640, 368, 600))
    stem = '1080p' if full_hd else 'wave' if args.action == 'wave' else 'small'
    clip = Path(args.fixtures) / (stem + '.h264')
    reference = Path(args.fixtures) / (stem + '.i420')
    if args.action in ('h264', 'h264-1080p', 'wave'):
        info = json.loads(run('ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                              '-of', 'json', str(clip)))['streams'][0]
        if (info['codec_name'], info['width'], info['height'], info['pix_fmt'],
                info['nb_read_frames']) != ('h264', width, height, 'yuv420p', str(frame_count)):
            raise ValueError('Unexpected single-instance 8-bit fixture dimensions or frame count')
        if args.action == 'h264' and sha(clip) != (
                '449bf8a077c6b4a9d2b356c644f373042ee0c7a0842e34e15e3f15acddcce9f8'):
            raise ValueError('Expected the identical vendor live-comparison H.264 sample')
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
            parameters = ['enable_t7=1']
            # Only an explicit higher stage may leave the eight-step limit.
            # Open still needs allow_t7_power and a successful full MDEC test.
            if args.action in ('mdec', 'compliance', 'h264', 'h264-1080p'):
                parameters.append('t7_snapshot_only=0')
            run('modprobe', 'aml-vdec-drv', *parameters)
            candidate = 'aml_vdec_drv'
        if args.action == 'probe':
            probe_without_power()
            if faulted():
                raise RuntimeError('Fault reported at probe')
        elif args.action == 'power':
            power_cycle()
        elif args.action == 'mdec':
            mdec_cycle()
        elif args.action == 'snapshot':
            outer_register_snapshot(args.payload)
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
                'filesink', 'location=' + str(output),
                timeout=30 if args.action == 'h264' else 15 if full_hd else 10)
            elapsed = time.monotonic() - started
            finished = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = finished.ru_utime + finished.ru_stime - usage.ru_utime - usage.ru_stime
            if output.read_bytes() != reference.read_bytes():
                raise ValueError('Decoded frames differ from software reference')
            print('EXACT_FRAMES_MATCH', hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)
            frame_size = width * height * 3 // 2
            frames = output.read_bytes()
            if len(frames) != frame_size * frame_count:
                raise ValueError('Unexpected number of complete I420 frames')
            for index in range(frame_count):
                digest = hashlib.md5(frames[index * frame_size:(index + 1) * frame_size]).hexdigest()
                print('FRAME_MD5', index, digest, flush=True)
            print('SHORT_CLIP_SECONDS', elapsed, 'including pipeline startup', flush=True)
            print('SHORT_CLIP_CPU_SECONDS', cpu, 'ONE_CORE_PERCENT', 100 * cpu / elapsed,
                  'FRAMES_PER_SECOND', frame_count / elapsed, flush=True)
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
    parser.add_argument('--validation-plan', type=Path,
                        help='Prepared compliance/Fluster window with exact kernel, input and tool identities')
    parser.add_argument('--validation-seconds', type=int, help=argparse.SUPPRESS)
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
        if args.validation_plan:
            def interrupted(signum, frame):
                # Let bounded_process terminate its separate decoder session
                # before the outer timeout's final SIGKILL.
                raise SystemExit(128 + signum)
            signal.signal(signal.SIGTERM, interrupted)
            acceptance_window(args)
            return
        # Remove experimental device factories with the temporary payload.
        os.environ['GST_REGISTRY'] = str(Path(args.payload) / 'gst-registry.bin')
        # Keep missing diagnostic tools in the temporary payload, off the rootfs
        # package database. Their shared libraries are checked before installation.
        tool_bin = Path(args.payload) / 'tools/usr/bin'
        if tool_bin.is_dir():
            os.environ['PATH'] = str(tool_bin) + os.pathsep + os.environ['PATH']
        board_window(args)
        return
    if not args.execute:
        if args.validation_plan:
            plan = json.loads(args.validation_plan.read_text())
            print(json.dumps({'action': args.action, 'offline': True, 'ssh': False,
                              'validation_plan': plan}, indent=2))
            return
        if args.action in ('fluster', 'performance'):
            print(json.dumps({'action': args.action, 'offline': True, 'ssh': False,
                              'requires': ['offline input/tool checksums', 'kernel manifest',
                                           'validation plan', 'existing board-window recovery proof'],
                              'order': ['board-queue', 'watchdog and exact kernel identity',
                                        'bounded single-stream tests; stop on first failure',
                                        'save raw results, including timeout and not-run',
                                        'board-window baseline and video recovery']}, indent=2))
            return
        print(json.dumps({'action': args.action, 'offline': True, 'ssh': False,
                          'order': ['heavy then board locks', 'RAM-only boot or supervised baseline recovery',
                                    'probe: gate off, EPERM, read-only SMC status',
                                    'power: explicit opt-in, one DOS read, verified power off',
                                    'snapshot: stop after step 8; read outer controls, then abort/power off',
                                    'mdec: thirteen separate steps; EN0 before domain, GCLK read before write',
                                    'compliance only after probe + power + mdec receipts',
                                    'stop clients', 'exclusive codec lease', args.action,
                                    'safe unload or RESET_REQUIRED', 'restore boot baseline',
                                    'encoding + HDMI + services + UDC + actual HID verification'],
                          'register_steps': dict(enumerate(REGISTER_STEPS, 1))}, indent=2))
        return
    if not (args.at_board or args.once_baseline) or args.manifest is None:
        parser.error('--execute requires --at-board or --once-baseline, and --manifest')
    proof = json.loads(args.manifest.read_text())
    if args.validation_plan:
        execute_acceptance(args, json.loads(args.validation_plan.read_text()), proof)
        return
    require_candidate(args.action, proof, once=bool(args.once_baseline))
    if args.action in ('fluster', 'performance'):
        parser.error(args.action + ' requires --validation-plan with offline prepared inputs')
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
    subprocess.run(['ssh', '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=3',
                    '-o', 'ServerAliveCountMax=2', '-o', 'BatchMode=yes', 'vim4', shlex.join(remote)],
                   input=source, text=True, check=True, timeout=180)


if __name__ == '__main__':
    main()
