#!/usr/bin/env python3
"""Exclusive Linux memory microbenchmark; no SSH, frequency writes or deployment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import tempfile
import threading
import time


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def snapshot():
    return dict(at=time.monotonic(),
                cpu={str(p): {n: read(p / n) for n in
                              ['scaling_governor', 'scaling_min_freq', 'scaling_max_freq',
                               'scaling_cur_freq', 'related_cpus']}
                     for p in Path('/sys/devices/system/cpu/cpufreq').glob('policy*')},
                thermal={p.name: {n: read(p / n) for n in ['type', 'temp']}
                         for p in Path('/sys/class/thermal').glob('thermal_zone*')},
                ddr=read('/sys/class/aml_ddr/freq'),
                ddr_devfreq={p.name: {n: read(p / n) for n in ['name', 'cur_freq', 'governor']}
                             for p in Path('/sys/class/devfreq').glob('*')
                             if any(s in p.name.lower() for s in ['ddr', 'dmc'])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tmpfs', type=Path, default=Path('/dev/shm'))
    parser.add_argument('--cpu', type=int, default=2)
    parser.add_argument('--repeats', type=int, choices=range(1, 10), default=5)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.cpu not in os.sched_getaffinity(0):
        parser.error('CPU must be in the current allowed CPU set')
    args.output.mkdir()  # Do not overwrite a previous run.
    original = sorted(os.sched_getaffinity(0))
    stop = threading.Event()
    samples = []
    initial = {name: read('/proc/' + name) for name in ['meminfo', 'vmstat', 'swaps', 'self/cgroup']}

    def sample():
        os.sched_setaffinity(0, original)
        while not stop.is_set():
            samples.append(snapshot())
            stop.wait(1)

    thread = None
    expired = threading.Event()
    code = None
    try:
        os.sched_setaffinity(0, {args.cpu})
        thread = threading.Thread(target=sample)
        thread.start()
        with tempfile.TemporaryDirectory(prefix='memory-bench-', dir=args.tmpfs) as temp:
            with (args.output / 'rows.jsonl').open('w') as log:
                child = subprocess.Popen([str(binary), temp, str(args.repeats)], stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True)

                def terminate():
                    expired.set()
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

                timer = threading.Timer(170, terminate)
                timer.start()
                try:
                    code = child.wait(timeout=173)
                except BaseException:
                    terminate()
                    child.wait(timeout=3)
                    raise
                finally:
                    timer.cancel()
    finally:
        stop.set()
        if thread:
            thread.join()
        os.sched_setaffinity(0, original)
        mappings = read('/proc/self/maps') or ''
        libc = {line.split()[-1] for line in mappings.splitlines() if 'libc.so' in line}
        metadata = dict(kernel=os.uname().release, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                        libc_sha256={p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                     for p in libc if Path(p).is_file()},
                        cpu=args.cpu, repeats=args.repeats, affinity_before=original,
                        affinity_restored=sorted(os.sched_getaffinity(0)), returncode=code,
                        timed_out=expired.is_set(), samples=samples,
                        initial=initial, mountinfo=read('/proc/self/mountinfo'),
                        cpuinfo=read('/proc/cpuinfo'),
                        mthp={str(p): read(p) for p in Path('/sys/kernel/mm/transparent_hugepage').glob('hugepages-*/enabled')},
                        cmdline=read('/proc/cmdline'), meminfo=read('/proc/meminfo'),
                        vmstat=read('/proc/vmstat'), swaps=read('/proc/swaps'),
                        thp=read('/sys/kernel/mm/transparent_hugepage/enabled'),
                        shmem_thp=read('/sys/kernel/mm/transparent_hugepage/shmem_enabled'),
                        zswap=read('/sys/module/zswap/parameters/enabled'))
        (args.output / 'state.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if code or expired.is_set():
        raise SystemExit('benchmark failed; retain rows.jsonl and state.json')
    rows = [json.loads(line) for line in (args.output / 'rows.jsonl').read_text().splitlines()]
    if len(rows) != args.repeats * 35 or any(row['ns'] <= 0 for row in rows):
        raise SystemExit('incomplete benchmark')
    if any(row['cpu_begin'] != args.cpu or row['cpu_end'] != args.cpu for row in rows):
        raise SystemExit('CPU placement mismatch; results are not qualified')
    groups = {}
    for row in rows:
        groups.setdefault((row['phase'], row['size']), []).append(row)
    distribution = []
    for (phase, size), group in sorted(groups.items()):
        values = sorted(row['ns'] for row in group)
        distribution.append(dict(phase=phase, size=size, samples=len(values),
                                 raw_ns=[row['ns'] for row in group],
                                 first_ns=group[0]['ns'], minimum_ns=values[0],
                                 mean_ns=statistics.mean(values), median_ns=statistics.median(values),
                                 p99_ns=values[-1], maximum_ns=values[-1]))
    # With at most nine samples nearest-rank P99 is the observed maximum.
    (args.output / 'distribution.json').write_text(json.dumps(distribution, indent=2) + '\n')


if __name__ == '__main__':
    main()
