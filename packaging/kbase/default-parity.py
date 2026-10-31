#!/usr/bin/env python3
"""Exclusive board window: identical idle history, bounded GPU probes, no governor writes.

Run under the board lock as root; --root holds run.py and the three compiled
probes. A fresh --output retains raw outputs, thermal samples and dmesg.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time


def snapshot():
    files = list(Path('/sys/class/thermal').glob('thermal_zone*/temp'))
    files += list(Path('/sys/class/thermal').glob('thermal_zone*/type'))
    for name in ('governor', 'polling_interval', 'cur_freq', 'available_frequencies'):
        files += list(Path('/sys/class/devfreq').glob('*/' + name))
    files += list(Path('/sys/class/mpgpu').glob('cur_freq'))
    files += list(Path('/sys/class/mpgpu').glob('utilization'))
    return {str(p): p.read_text().strip() for p in files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.root.resolve()
    report = {'kernel': os.uname().release, 'samples': [], 'idleSeconds': 300,
              'intervalSeconds': 2, 'repetitions': 7, 'thermal': []}
    deadline = time.monotonic() + 570
    initial = subprocess.check_output(['dmesg'], text=True)

    def guard():
        log = subprocess.check_output(['dmesg'], text=True)
        delta = log[len(initial):] if log.startswith(initial) else log
        if any(t in delta for t in ('WARNING:', 'BUG:', 'Oops:', 'GPU Fault ',
                                    'Unhandled Page fault', 'GPU fault 0x',
                                    'Job has been on the GPU for too long')):
            raise RuntimeError('kernel/GPU fault; stop this window')
        if time.monotonic() >= deadline:
            raise RuntimeError('whole-phase deadline')

    def run(name, command, graphics='icd', budget=30):
        guard()
        time.sleep(2)
        started = time.monotonic()
        with (args.output / (name + '.txt')).open('w') as stream:
            process = subprocess.Popen(['python3', str(root / 'run.py'),
                                        '--graphics', graphics, '--', *map(str, command)],
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    guard()
                    if time.monotonic() - started > budget:
                        raise RuntimeError(name + ': timeout')
                    time.sleep(.2)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=3)
        guard()
        text = (args.output / (name + '.txt')).read_text()
        value = None
        if name.startswith('dma-'):
            value = float(re.search(r'submit_wait_ms=([\d.]+)', text)[1])
        elif name.startswith('gles-'):
            match = re.search(r'frames=(\d+) seconds=([\d.]+)', text)
            if 'Mali-G52' not in text:
                raise RuntimeError('Unexpected GLES device')
            value = int(match[1]) / float(match[2])
        elif name.startswith('cl-latency-'):
            value = float(re.search(r'Kernel launch latency\s*:\s*([\d.]+)', text)[1])
        elif name.startswith('cl-sp-'):
            value = float(re.search(r'^\s+float\s*:\s*([\d.]+)', text, re.M)[1])
        report['samples'].append({'name': name, 'exit': process.returncode, 'value': value,
                                  'seconds': time.monotonic() - started,
                                  'state': snapshot()})
        if process.returncode:
            raise RuntimeError(name + ': exit ' + str(process.returncode))

    try:
        # Only cached sysfs telemetry; device queries may change idle history.
        for _ in range(60):
            report['thermal'].append({'time': time.time(), 'phase': 'idle', 'state': snapshot()})
            guard()
            time.sleep(5)
        report['thermal'].append({'time': time.time(), 'phase': 'idle-end', 'state': snapshot()})
        clpeak = Path('/opt/vim4-mesa-26.2.6/bin/clpeak')
        for i in range(7):
            run(f'dma-{i}', [root / 'mali-dma-probe', root / 'mali-dma-probe.spv',
                            '/dev/dma_heap/heap-gfx', '1'])
            run(f'gles-{i}', [root / 'gpu-probe', '5', '/dev/dri/card0'], 'direct')
            run(f'cl-latency-{i}', [clpeak, '--platform', '0', '--device', '0', '--kernel-latency'])
            run(f'cl-sp-{i}', [clpeak, '--platform', '0', '--device', '0', '--compute-sp'], budget=45)
        report['thermal'].append({'time': time.time(), 'phase': 'load-end', 'state': snapshot()})
        report['summary'] = {}
        for kind in ('dma', 'gles', 'cl-latency', 'cl-sp'):
            values = sorted(s['value'] for s in report['samples']
                            if s['name'].rsplit('-', 1)[0] == kind)
            report['summary'][kind] = {'median': statistics.median(values),
                                       'p95NearestRank': values[-1], 'n': len(values)}
        report['p95Method'] = 'nearest rank; with seven samples P95 is the maximum, low confidence'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (args.output / 'dmesg.txt').write_text(subprocess.check_output(['dmesg'], text=True))
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
