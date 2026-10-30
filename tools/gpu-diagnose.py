#!/usr/bin/env python3
"""Exclusive GPU-only diagnostic. Run under the board/heavy locks; no service or MMIO access.

Copy alongside gpu-compare.py. --frequency/--pm/--profiling are temporary sysfs
overrides restored on completion, failure and TERM. Never writes voltages or PWM.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def read(path):
    try:
        return path.read_text().strip()
    except (OSError, UnicodeError):
        return None


def fdinfo(pid):
    clients = {}
    for path in Path(f'/proc/{pid}/fdinfo').glob('*'):
        values = {}
        for line in (read(path) or '').splitlines():
            key, _, value = line.partition(':')
            if key.startswith('drm-'):
                values[key] = value.strip()
        if values.get('drm-driver') == 'panfrost' and 'drm-client-id' in values:
            clients[values['drm-client-id']] = values
    return clients


def activity(samples, ticks):
    intervals = []
    for before, after in zip(samples, samples[1:]):
        elapsed = after['time'] - before['time']
        engines = {}
        for client in before['fdinfo'].keys() & after['fdinfo'].keys():
            a, b = before['fdinfo'][client], after['fdinfo'][client]
            for key in a.keys() & b.keys():
                if key.startswith('drm-engine-'):
                    delta = int(b[key].split()[0]) - int(a[key].split()[0])
                    if delta >= 0:
                        engines[key] = engines.get(key, 0) + delta
        busy = min(100, 100 * max(engines.values()) / (elapsed * 1e9)) if engines else None
        cpu = None
        if before['cpu_stat'] and after['cpu_stat']:
            a = before['cpu_stat'].rsplit(')', 1)[1].split()
            b = after['cpu_stat'].rsplit(')', 1)[1].split()
            cpu = 100 * (int(b[11]) + int(b[12]) - int(a[11]) - int(a[12])) / ticks / elapsed
        intervals.append({'seconds': elapsed, 'engine_busy_estimate_percent': busy,
                          'process_one_core_cpu_percent': cpu})
    return intervals


def run(command, env, root, seconds):
    samples = []
    with tempfile.TemporaryFile(mode='w+') as stream:
        process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        start = time.monotonic()
        error = None
        try:
            while process.poll() is None:
                if time.monotonic() - start > seconds:
                    raise TimeoutError('GPU diagnostic deadline exceeded')
                samples.append({'time': time.monotonic(), 'freq': read(root / 'cur_freq'),
                                'runtime': read(root / 'device/power/runtime_status'),
                                'fdinfo': fdinfo(process.pid),
                                'cpu_stat': read(Path(f'/proc/{process.pid}/stat'))})
                time.sleep(.2)
        except (TimeoutError, InterruptedError) as failure:
            error = str(failure)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        stream.seek(0)
        return {'samples': samples, 'exit': process.returncode, 'output': stream.read(), 'error': error}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('vendor', 'system', 'private'), required=True)
    parser.add_argument('--runtime', type=Path, default=Path('/opt/vim4-mesa-26.2.6'))
    parser.add_argument('--devfreq', type=Path, default=Path('/sys/class/devfreq/fe400000.gpu'))
    parser.add_argument('--frequency', type=int, help='Pin min/max to one advertised frequency')
    parser.add_argument('--pm', choices=('on', 'auto'))
    parser.add_argument('--profiling', action='store_true', help='Separate profiling run; affects cost')
    parser.add_argument('--unroll128', action='store_true')
    parser.add_argument('--seconds', type=int, choices=range(1, 61), default=20)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('a probe command after -- is required')
    command = args.command[1:] if args.command[0] == '--' else args.command
    spec = importlib.util.spec_from_file_location('compare', Path(__file__).with_name('gpu-compare.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = module.environment(args.mode, args.runtime)
    if args.unroll128:
        env['GPU_UNROLL128'] = '1'
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.devfreq
    saved = []
    report = {'command': command, 'mode': args.mode, 'ticks_per_second': os.sysconf('SC_CLK_TCK'),
              'before_trans_stat': read(root / 'trans_stat'), 'overrides': []}

    def change(path, value):
        old = path.read_text().strip()
        path.write_text(str(value))
        saved.append((path, old))
        report['overrides'].append({'path': str(path), 'before': old, 'requested': str(value)})

    def terminate(*_):
        raise InterruptedError('terminated; restoring GPU controls')

    signal.signal(signal.SIGTERM, terminate)
    try:
        if args.frequency:
            frequencies = (root / 'available_frequencies').read_text().split()
            if str(args.frequency) not in frequencies:
                raise ValueError('frequency is not in advertised OPPs')
            # Expand the maximum first; min may not exceed the previous maximum.
            maximum = int((root / 'max_freq').read_text())
            if args.frequency > maximum and maximum:
                change(root / 'max_freq', args.frequency)
                change(root / 'min_freq', args.frequency)
            else:
                change(root / 'min_freq', args.frequency)
                change(root / 'max_freq', args.frequency)
        if args.pm:
            change(root / 'device/power/control', args.pm)
        if args.profiling:
            change(root / 'device/profiling', 1)
        report['result'] = run(command, env, root, args.seconds + 15)
        if report['result']['error']:
            report['error'] = report['result']['error']
        report['activity_intervals'] = activity(report['result']['samples'], report['ticks_per_second'])
    except Exception as error:
        report['error'] = str(error)
    finally:
        report['after_trans_stat'] = read(root / 'trans_stat')
        failures = []
        for path, value in reversed(saved):
            try:
                path.write_text(value)
            except OSError as error:
                failures.append(f'{path}: {error}')
        report['restore_errors'] = failures
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return int(bool(report.get('error') or report['restore_errors'] or report.get('result', {}).get('exit')))


if __name__ == '__main__':
    raise SystemExit(main())
