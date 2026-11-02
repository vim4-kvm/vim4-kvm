#!/usr/bin/env python3
"""Quick video experiment support; dispatch latency includes the source HTTP leg.

MCP and native sampling require a board-queue ticket. The source server uses no HID.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import math
import shlex
import signal
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('board_window', str(ROOT / 'tools/board-window'))
spec = importlib.util.spec_from_loader(loader.name, loader)
bw = importlib.util.module_from_spec(spec)
loader.exec_module(bw)

NATIVE_WORK_SECONDS = 30 + 3 * (85 + 20)  # upload, bounded bench and result copies
SERVICE_RECOVERY_SECONDS = 40
RECEIVER_WORK_SECONDS = 111  # startup, bounded receiver, local tunnel teardown
BASELINE_RECOVERY_SECONDS = 240
PM_PHASE_SECONDS = {'idle': 300, 'signal': 300, 'h264': 600, 'h265': 600}


def require_budget(queue, ticket, seconds):
    item = queue.read(ticket)
    remaining = item['started'] + item['seconds'] - time.time()
    if item['state'] != 'held' or item['heavy'] or remaining < seconds:
        raise RuntimeError(f'board lease cannot cover {seconds}s of work/recovery (remaining {remaining:.1f}s)')


def cleanup(output, actions):
    """Attempt every cleanup, retaining the measurement exception as primary."""
    primary = sys.exception()
    errors = []
    for name, action in actions:
        try:
            action()
        except Exception as error:
            error.add_note(name)
            errors.append(error)
    if errors:
        message = '; '.join(str(error) for error in errors)
        path = output / 'cleanup-errors.json'
        records = json.loads(path.read_text()) if path.exists() else []
        path.write_text(json.dumps(records + [
            dict(error=str(error), step=error.__notes__[-1]) for error in errors]))
        if primary is not None:
            primary.add_note('Cleanup errors: ' + message)
        else:
            raise ExceptionGroup('Cleanup failed', errors)


def restore_owned(queue, ticket, seconds, output, what, action):
    # An expired lease can already belong to the next sampler. Keep an explicit
    # handoff record instead of issuing an unowned service restart/reboot.
    try:
        require_budget(queue, ticket, seconds)
        action()
    except Exception as error:
        (output / 'recovery-required.json').write_text(json.dumps(dict(
            recovery=what, error=str(error), ticket=ticket)))
        raise


def serve(output, port):
    with output.open('x') as log:
        class Handler(BaseHTTPRequestHandler):
            sequence = 0

            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == '/tick':
                    Handler.sequence += 1
                    stamp = time.time_ns() / 1e6
                    record = dict(id=Handler.sequence & 65535, sourceMs=stamp, drawEndMs=stamp)
                    log.write(json.dumps(record) + '\n')
                    log.flush()
                    body = json.dumps(record).encode()
                    content_type = 'application/json'
                elif self.path == '/':
                    body = (ROOT / 'tools/perf-motion.html').read_bytes()
                    content_type = 'text/html'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        HTTPServer(('0.0.0.0', port), Handler).serve_forever()


def mcp(action, arguments, output, url):
    bw.require_board()
    credentials = json.loads(bw.ssh('vim4', 'sudo -n cat /var/lib/one-kvm/mcp/credentials.json'))
    # Do not print credentials or pass them as process arguments.
    key = credentials.get('token') or credentials.get('api_key') or credentials.get('bearer_token')
    if not key:
        raise ValueError('Unknown credential fields: ' + ','.join(credentials))
    client = bw.MCP(url, key)
    if action == 'screenshot':
        client.screenshot(output)
    elif action == 'list':
        client.initialize()
        output.write_text(json.dumps(client.rpc('tools/list', {})))
    else:
        output.write_text(json.dumps(client.call(action, arguments)))


def bench_command(backend, remote, codec, secondary, *, width=1920, height=1080,
                  frames=1800, deadline=65):
    env = ('GST_PLUGIN_PATH=/usr/lib/vim4-kvm/gstreamer-1.0 LD_LIBRARY_PATH=/opt/vim4-onekvm/lib'
           if backend == 'stock' else 'GST_PLUGIN_PATH=/usr/lib/vim4-kvm/mainline-gstreamer-1.0')
    if secondary:
        env = ('GST_PLUGIN_PATH=/opt/vim4-onekvm/lib/gstreamer-1.0:/usr/lib/vim4-kvm/gstreamer-1.0 '
               'LD_LIBRARY_PATH=/opt/vim4-onekvm/lib VIM4_SECONDARY_HDMI_CAPTURE=1 '
               'GST_V4L2_PREFER_CONTIGUOUS=1')
    return (f'env {env} GST_REGISTRY={remote}/registry.bin timeout -k 3 {deadline + 10} {remote}/bench '
            f'--exclusive --backend={backend} --codec={codec} --warmup=120 --frames={frames} '
            f'--width={width} --height={height} --bitrate=12000000 --gop=60 --timeout={deadline} '
            f'--output={remote}/{codec}.json' + (' --secondary' if secondary else ''))


def native(backend, output, reserve_seconds=0):
    queue, ticket = bw.require_board()
    require_budget(queue, ticket, NATIVE_WORK_SECONDS + SERVICE_RECOVERY_SECONDS + reserve_seconds)
    output.mkdir(exist_ok=False)
    remote = '/var/tmp/p0-2-' + str(time.time_ns())
    bw.ssh('vim4', 'mkdir ' + remote)
    subprocess.run(['scp', str(ROOT / 'build/p0-2/vim4-driver-bench'), 'vim4:' + remote + '/bench'], check=True, timeout=30)
    active = bw.ssh('vim4', 'systemctl is-active one-kvm').strip() == 'active'
    secondary = (backend == 'stock' and bw.ssh(
        'vim4', 'cat /sys/module/aml_media/parameters/vdin0_native_hdr').strip() == 'Y')
    try:
        require_budget(queue, ticket, NATIVE_WORK_SECONDS + SERVICE_RECOVERY_SECONDS + reserve_seconds)
        bw.ssh('vim4', 'sudo -n systemctl stop one-kvm')
        queue.sampling(ticket, True)
        (output / 'sampling.json').write_text(json.dumps(queue.read(ticket)))
        for codec in ('capture', 'h264', 'h265'):
            require_budget(queue, ticket, 85 + 20 + SERVICE_RECOVERY_SECONDS + reserve_seconds)
            command = bench_command(backend, remote, codec, secondary)
            try:
                text = bw.ssh('vim4', command, timeout=85)
                (output / (codec + '.stdout')).write_text(text)
            finally:
                cleanup(output, [('copy benchmark result', lambda: subprocess.run(
                    ['scp', 'vim4:' + remote + '/' + codec + '.json', str(output)], check=False, timeout=20))])
    finally:
        cleanup(output, [('sampling off', lambda: queue.sampling(ticket, False)),
            ('restore service', lambda: restore_owned(queue, ticket, SERVICE_RECOVERY_SECONDS, output,
                'start previously active one-kvm',
                lambda: bw.ssh('vim4', 'sudo -n systemctl start one-kvm', timeout=40)) if active else None)])


@contextmanager
def pm_cancellation():
    # Short mutations and rollback run to completion. Interrupt only waits
    # whose remote owner is already known, then unwind under the same ticket.
    cancelled = False
    interruptible = False

    def check():
        if cancelled:
            raise InterruptedError('PM window cancelled')

    def receive(signum, frame):
        nonlocal cancelled
        cancelled = True
        if interruptible:
            check()

    def wait(action):
        nonlocal interruptible
        interruptible = True
        try:
            check()
            return action()
        finally:
            interruptible = False

    previous = {sig: signal.signal(sig, receive) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield check, wait
        check()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def pm_ssh(command, timeout=15):
    return bw.ssh('vim4', command, timeout=timeout, isolated=True)


def pm_block(output):
    boot = pm_ssh('cat /proc/sys/kernel/random/boot_id').strip()
    policies = dict(line.split() for line in pm_ssh(
        'for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do '
        'value=$(cat "$f") || exit 1; echo "$f $value"; done').splitlines())
    if not boot or not policies:
        raise RuntimeError('Missing boot ID or CPU policy')
    actual = dict(boot_id=boot, governors=policies)
    baseline = output.parent / 'boot-policies.json'
    if baseline.exists():
        if json.loads(baseline.read_text()) != actual:
            (output / 'rejected-boot-policies.json').write_text(json.dumps(actual))
            raise RuntimeError('Boot ID or policy changed within PM block')
    else:
        baseline.write_text(json.dumps(actual))
    return actual


def pm_interval(output, codec):
    bench = json.loads((output / (codec + '.json')).read_text())
    start = bench['measurement_start_monotonic_us'] * 1000
    end = bench['measurement_end_monotonic_us'] * 1000
    with (output / 'pm.jsonl').open() as stream:
        stamps = [json.loads(line)['monotonic_ns'] for line in stream]
    common = [stamp for stamp in stamps if start <= stamp <= end]
    if not (bench['success'] and len(common) >= 2 and stamps[0] <= start < end <= stamps[-1]):
        raise RuntimeError('PM telemetry does not cover successful bench interval')
    return dict(start_ns=common[0], end_ns=common[-1], samples=len(common))


def pm_ready():
    # A simple unit may report active before its HTTP server is listening.
    probe = "import json, urllib.request; s=json.load(urllib.request.urlopen(" \
            "'http://127.0.0.1:8081/api/stream/status',timeout=2)); assert 'clients' in s and 'state' in s"
    command = 'systemctl is-active --quiet one-kvm && python3 -c ' + shlex.quote(probe)
    pm_ssh('timeout 20 sh -c ' + shlex.quote('until ' + command + '; do sleep 1; done'), timeout=25)


def pm_phase(args):
    with pm_cancellation() as (check, wait):
        run_pm_phase(args, check, wait)


def run_pm_phase(args, check, wait):
    seconds = PM_PHASE_SECONDS[args.phase]
    load = args.phase in ('h264', 'h265')
    frames = seconds * 60
    deadline = math.ceil((frames + 120) / 57) + 20
    work_timeout = deadline + 35 if load else seconds + 10
    # Stop unit, end probe, restore both policies/service/API, fetch evidence, remove directory.
    finish_budget = 180
    queue, ticket = bw.require_board()
    require_budget(queue, ticket, work_timeout + finish_budget + 120)
    release = pm_ssh('uname -r').strip()
    edge = release == '7.3.0-vim4kvm-uhd6+'
    if not (edge or release.startswith('5.15.')) or (args.schedutil and not edge):
        raise RuntimeError(f'Unexpected kernel for PM group: {release}')
    backend = 'edge' if edge else 'stock'
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    unit = 'p0-2-pm-' + str(time.time_ns())
    remote = '/var/tmp/' + unit
    phase = dict(release=release, phase=args.phase, seconds=seconds, schedutil=args.schedutil,
                 board_power='缺测', **pm_block(output))

    def save():
        (output / 'phase.json').write_text(json.dumps(phase, indent=2))

    def check_state(point, service):
        try:
            state = json.loads(pm_ssh(f'python3 {remote}/sensors.py --phase-state {backend}'))
            phase[point] = state
            hdmi = state['hdmi']
            if not (hdmi['signal'] and not hdmi.get('interlaced') and (hdmi['width'], hdmi['height']) == (3840, 2160)
                    and abs(hdmi['refreshHz'] - 60) <= 0.5):
                raise RuntimeError(f'{point}: expected locked 3840x2160p60, got {hdmi}')
            if state['one_kvm'] != service or (service == 'active' and
                    any(state[key] != 0 for key in ('clients', 'webrtc_sessions', 'uu_desktop_sessions'))):
                raise RuntimeError(f'{point}: expected one-kvm {service} with no viewers, got {state}')
        except Exception as error:
            phase[point + '_error'] = str(error)
            raise
        finally:
            save()

    def set_governor(path, value):
        path, value = shlex.quote(path), shlex.quote(value)
        pm_ssh(f'echo {value} | sudo -n tee {path} >/dev/null && test "$(cat {path})" = {value}')

    def restart():
        pm_ssh('sudo -n systemctl start one-kvm')
        pm_ready()

    def stop_work():
        pm_ssh(f'if [ "$(systemctl show {unit}.service -p LoadState --value)" != not-found ]; '
               f'then sudo -n systemctl stop {unit}.service || exit 1; fi; touch {remote}/stopped')

    def scp(*paths):
        subprocess.run(['scp', *paths], check=True, timeout=30, start_new_session=True)

    def finish_files():
        if started:
            require_budget(queue, ticket, 45)
            names = ['pm.jsonl', 'stdout'] + ([args.phase + '.json'] if load else [])
            scp(*['vim4:' + remote + '/' + name for name in names], str(output))
        require_budget(queue, ticket, 15)
        pm_ssh('rm -rf -- ' + remote)
        phase.pop('retained_remote', None)

    restore = []
    started = False
    service = 'active' if args.phase == 'signal' else 'inactive'
    try:
        phase['retained_remote'] = remote
        pm_ssh('mkdir ' + remote)
        scp(str(ROOT / 'tools/perf-sensors.py'), 'vim4:' + remote + '/sensors.py')
        sampler = f'python3 {remote}/sensors.py --gpu-devfreq-only --output={remote}/pm.jsonl'
        script = f'{sampler} --seconds={seconds}'
        if load:
            scp(str(ROOT / 'build/p0-2/vim4-driver-bench'), 'vim4:' + remote + '/bench')
            secondary = not edge and pm_ssh('cat /sys/module/aml_media/parameters/vdin0_native_hdr').strip() == 'Y'
            bench = bench_command(backend, remote, args.phase, secondary, width=3840, height=2160,
                                  frames=frames, deadline=deadline) + ' --skip-debug-clocks'
            script = (f'{sampler} --seconds={work_timeout} --bench-done={remote}/done & sampler=$!; '
                      f'while [ ! -s {remote}/pm.jsonl ]; do kill -0 "$sampler" || exit 1; sleep 0.1; done; '
                      f'{bench}; rc=$?; touch {remote}/done; wait "$sampler" || exit 1; exit "$rc"')
        check_state('preflight', 'active')
        try:
            wait(lambda: queue.sampling(ticket, True))
            require_budget(queue, ticket, work_timeout + finish_budget + 55)
            (output / 'sampling.json').write_text(json.dumps(queue.read(ticket)))
            if service == 'inactive':
                check_state('before_stop', 'active')
                check()
                restore.append(('restart one-kvm and verify API', restart))
                pm_ssh('sudo -n systemctl stop one-kvm')
            check_state('start', service)
            if args.schedutil:
                for path, previous in phase['governors'].items():
                    check()
                    restore.append(('restore ' + path, lambda p=path, v=previous: set_governor(p, v)))
                    set_governor(path, 'schedutil')
            check()
            require_budget(queue, ticket, work_timeout + finish_budget)
            # Start synchronously, so cancellation always has a known unit to stop.
            started = True
            body = f'( {script} ) >{remote}/stdout 2>&1; echo $? >{remote}/result'
            pm_ssh(f'sudo -n systemd-run --quiet --collect --unit={unit} --uid="$(id -un)" '
                   f'-p Type=exec -p TimeoutStopSec=4 -p RuntimeMaxSec={work_timeout} '
                   '/bin/sh -c ' + shlex.quote(body))
            monitor = (f'while [ ! -s {remote}/result ]; do [ -d {remote} ] && [ ! -e {remote}/stopped ] '
                       f'|| exit 1; sleep 1; done; test "$(cat {remote}/result)" = 0')
            wait(lambda: pm_ssh('timeout ' + str(work_timeout) + ' sh -c ' + shlex.quote(monitor),
                                timeout=work_timeout + 5))
        finally:
            actions = []
            if started:
                actions += [('stop remote workload', lambda: restore_owned(queue, ticket, 15, output,
                               'stop ' + unit, stop_work)), ('qualify phase end', lambda: check_state('end', service))]
            actions += [(name, lambda n=name, a=action: restore_owned(queue, ticket, 45, output, n, a))
                        for name, action in reversed(restore)]
            if service == 'active' and started:
                actions.append(('verify one-kvm API', lambda: restore_owned(
                    queue, ticket, 25, output, 'verify one-kvm active and API ready', pm_ready)))
            cleanup(output, actions + [('sampling off', lambda: queue.sampling(ticket, False))])
    finally:
        try:
            cleanup(output, [('retrieve evidence and remove remote directory', finish_files)])
        finally:
            save()
    if load:
        phase['common_interval'] = pm_interval(output, args.phase)
        save()


def window(args):
    """One bounded sample, with candidate recovery inside the same lease."""
    queue, ticket = bw.require_board()
    started = time.monotonic()
    output = ROOT / 'logs/p0-2-quick' / args.label
    output.mkdir(exist_ok=False)
    tool = [str(ROOT / 'tools/board-window'), '--window', 'p0-2-quick',
            '--device', '/dev/cu.usbserial-1100']

    def step(name, command, timeout):
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

    candidate_started = False
    try:
        if args.candidate:
            require_budget(queue, ticket, 480 + BASELINE_RECOVERY_SECONDS)
            candidate_started = True
            step('boot', tool + ['boot-candidate', str(args.candidate), '--sha256', args.sha256, '--reuse-staged'], 480)
        step('before', tool + ['collect', '--readonly'], 30)
        if args.candidate and time.monotonic() - started > 200:
            raise RuntimeError('Boot used sampling budget; reserve time for baseline recovery')
        recovery_seconds = BASELINE_RECOVERY_SECONDS if args.candidate else 0
        native(args.backend, output / 'native', reserve_seconds=RECEIVER_WORK_SECONDS + 30 + recovery_seconds)
        require_budget(queue, ticket, RECEIVER_WORK_SECONDS + 30 + recovery_seconds)
        tunnel = subprocess.Popen(['ssh', '-o', 'ExitOnForwardFailure=yes', '-NT', '-L',
                                   '127.0.0.1:18082:127.0.0.1:8081', 'vim4'])
        try:
            time.sleep(1)
            queue.sampling(ticket, True)
            (output / 'sampling-receiver.json').write_text(json.dumps(queue.read(ticket)))
            step('receiver', ['node', str(ROOT / 'tools/latency-receiver.mjs'),
                             'http://127.0.0.1:18082', '30', '--one-kvm', '--local-backend',
                             '--expect-codec=h264', '--marker-y=540'], 100)
        finally:
            cleanup(output, [('sampling off', lambda: queue.sampling(ticket, False)),
                ('terminate tunnel', tunnel.terminate), ('reap tunnel', lambda: tunnel.wait(timeout=10))])
        step('after', tool + ['collect', '--readonly'], 30)
    finally:
        if candidate_started and (ROOT / 'logs/p0-2-quick/baseline-proof.json').exists():
            cleanup(output, [('return baseline', lambda: restore_owned(queue, ticket, BASELINE_RECOVERY_SECONDS,
                output, 'return baseline', lambda: step('return', tool + ['return-baseline'], 240)))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('source')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--port', type=int, default=18090)
    p = commands.add_parser('pm-phase')
    p.add_argument('phase', choices=PM_PHASE_SECONDS)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--schedutil', action='store_true')
    p = commands.add_parser('window')
    p.add_argument('--label', required=True)
    p.add_argument('--backend', choices=('stock', 'edge'), required=True)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--sha256')
    p = commands.add_parser('mcp')
    p.add_argument('action')
    p.add_argument('--url', default='http://192.168.50.210:8080/api/mcp')
    p.add_argument('--arguments', type=json.loads, default={})
    p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('native')
    p.add_argument('--backend', choices=('stock', 'edge'), required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'source':
        serve(args.output, args.port)
    elif args.command == 'pm-phase':
        pm_phase(args)
    elif args.command == 'mcp':
        mcp(args.action, args.arguments, args.output, args.url)
    elif args.command == 'native':
        native(args.backend, args.output)
    else:
        window(args)


if __name__ == '__main__':
    main()
