#!/usr/bin/env python3
"""Prepared board-window checks; never acquires a board window itself.

Run only after the coordinator reserves the board. sample observes an already
running workload until a stable five-minute window is found. prepare and compare are offline. Control phases change thermal
emulation, fan settings or system sleep and restore their temporary settings.
"""
import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import signal
import struct
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, '/usr/lib/vim4-kvm/python')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'board'))
from vim4fan import SENSORS, snapshot

THERMAL = Path('/sys/class/thermal')
DUTIES = (5, 10, 15, 20, 25, 30, 35, 43, 52, 61, 70, 77, 85, 92, 100)
MIN_WARMUP = 180
MEASUREMENT_SECONDS = 300
SIDE_SECONDS = 900


def prepare(args):
    """Validate a supplied RAM archive locally; never build or contact a board."""
    bundle = args.ram_package.resolve()
    with bundle.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != args.sha256:
        raise ValueError('RAM archive SHA256 differs from the supplied trusted digest')
    path = Path(__file__).resolve().with_name('board-window')
    loader = importlib.machinery.SourceFileLoader('fan_board_window', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    window = importlib.util.module_from_spec(spec)
    loader.exec_module(window)
    candidate = window.validate_bundle(bundle)
    baseline = window.once.formal_baseline()
    if candidate['release'] != args.release:
        raise ValueError('RAM archive release differs from --release')
    if candidate.get('baseline_release', baseline['release']) != baseline['release'] or \
            candidate.get('baseline_id', baseline['build_id']) != baseline['build_id']:
        raise ValueError('RAM archive was prepared for a different retained baseline')
    plan = dict(candidate=dict(package=str(bundle), sha256=digest, release=args.release,
                               build_id=candidate['build_id'], source=candidate.get('source')),
                baseline=dict(release=baseline['release'], build_id=baseline['build_id']),
                boot_command=['tools/board-window', 'boot-candidate', str(bundle), '--sha256', digest],
                recovery_command=['tools/board-window', 'return-baseline', '--video-check'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + '\n')


def running_identity(root=Path('/')):
    notes = (root / 'sys/kernel/notes').read_bytes()
    offset, build_id = 0, None
    while offset + 12 <= len(notes):
        namesize, size, kind = struct.unpack_from('<III', notes, offset)
        offset += 12
        name = notes[offset:offset + namesize].rstrip(b'\0')
        offset += (namesize + 3) & ~3
        value = notes[offset:offset + size]
        offset += (size + 3) & ~3
        if name == b'GNU' and kind == 3:
            build_id = value.hex()
    if build_id is None:
        raise ValueError('Running kernel has no GNU build ID')
    return dict(release=(root / 'proc/sys/kernel/osrelease').read_text().strip(), build_id=build_id)


def verify_identity(plan, role, actual):
    expected = plan['baseline' if role in ('baseline', 'returned') else 'candidate']
    if any(actual[key] != expected[key] for key in ('release', 'build_id')):
        raise ValueError(f'Running {role} release/build ID differs from supplied plan')


def assess_window(readings, started, end_seconds):
    """Use five complete time buckets; sampling overhead must not move boundaries."""
    start_seconds = end_seconds - MEASUREMENT_SECONDS
    minutes = [[] for _ in range(5)]
    for reading in readings:
        offset = reading['monotonic'] - started - start_seconds
        if 0 <= offset < MEASUREMENT_SECONDS:
            minutes[int(offset // 60)].append(reading)
    complete = all(minutes) and sum(map(len, minutes)) >= 120
    means = {kind: [sum(r['temperatures'][kind] for r in minute) / len(minute)
                    for minute in minutes] for kind in SENSORS} if complete else {}
    ranges = {kind: max(values) - min(values) for kind, values in means.items()}
    return dict(start_seconds=start_seconds, end_seconds=end_seconds,
                minute_means=means, ranges=ranges,
                stable=bool(complete and all(value <= 500 for value in ranges.values())))


def select_measurement(readings, started, elapsed):
    """Replay the first eligible stable window, without discarding its early minutes."""
    for end in range(MIN_WARMUP + MEASUREMENT_SECONDS, min(int(elapsed), SIDE_SECONDS) + 1, 60):
        window = assess_window(readings, started, end)
        if window['stable']:
            return window
    return None


def adaptive_sample(read, *, clock=time.monotonic, sleep=time.sleep, progress=lambda check: None):
    """Retain the whole history, checking once per minute through the 15-minute cap."""
    started = clock()
    readings, checks = [], []
    next_check = MIN_WARMUP + MEASUREMENT_SECONDS
    while True:
        if clock() >= started + next_check:
            window = assess_window(readings, started, next_check)
            checks.append(window)
            progress(window)
            if window['stable'] or next_check == SIDE_SECONDS:
                return dict(started_monotonic=started, elapsed=clock() - started,
                            readings=readings, checks=checks,
                            measurement=window if window['stable'] else None)
            next_check += 60
        state = read()
        state['monotonic'] = clock()
        readings.append(state)
        sleep(max(0, min(1, started + next_check - clock())))


def fan_device():
    return next(p for p in THERMAL.glob('cooling_device*')
                if (p / 'type').read_text().strip() == 'khadas-mcu-fan')


def zones():
    result = { (p / 'type').read_text().strip(): p for p in THERMAL.glob('thermal_zone*') }
    assert all(kind in result for kind in SENSORS), 'Six thermal zones must be registered'
    return [result[kind] for kind in SENSORS]


def trips(zone, fan):
    ids = sorted({int((zone / (p.name + '_trip_point')).read_text())
                  for p in zone.glob('cdev*') if p.is_symlink() and p.resolve() == fan.resolve()})
    assert len(ids) == 15, f'{zone}: expected 15 fan maps'
    assert all((zone / f'trip_point_{i}_type').read_text().strip() == 'active' for i in ids)
    assert all(int((zone / f'trip_point_{i}_hyst').read_text()) == 0 for i in ids)
    return [zone / f'trip_point_{i}_temp' for i in ids]


def expect(fan, target):
    deadline = time.monotonic() + 2
    while int((fan / 'cur_state').read_text()) != target:
        if time.monotonic() >= deadline:
            raise AssertionError(f'Fan did not reach {target}% within 2 seconds')
        time.sleep(.02)


def emulation():
    fan, sensors = fan_device(), zones()
    assert int((fan / 'max_state').read_text()) == 100
    assert not snapshot()['sensor_fault']
    for zone in sensors:
        assert (zone / 'policy').read_text().strip() == 'step_wise'
        assert (zone / 'emul_temp').exists(), 'CONFIG_THERMAL_EMULATION required'
    def inject(zone, temperature):
        (zone / 'emul_temp').write_text(f'{temperature}\n')
    # emul_temp is write-only. This phase requires an otherwise non-emulating
    # board; zero restores actual measurements even if a check fails.
    try:
        tables = [[int(p.read_text()) for p in trips(zone, fan)] for zone in sensors]
        assert all(table == tables[0] for table in tables)
        cold = min(tables[0][0] - 1000, 40000)
        for zone in sensors:
            inject(zone, cold)
        expect(fan, 0)
        for zone, table in zip(sensors, tables):
            for indexes in (range(15), range(14, -1, -1)):
                for i in indexes:
                    for temperature in (table[i] - 1, table[i], table[i] + 1):
                        inject(zone, temperature)
                        target = max((d for t, d in zip(table, DUTIES) if temperature >= t), default=0)
                        expect(fan, target)
            inject(zone, cold)
            expect(fan, 0)
        for hot in sensors:
            inject(hot, 100000)
            expect(fan, 100)
            for other in sensors:
                if other != hot:
                    inject(other, cold)
                    expect(fan, 100)
            inject(hot, cold)
        inject(sensors[0], tables[0][6])
        inject(sensors[1], tables[0][10])
        expect(fan, 70)
        inject(sensors[1], cold)
        expect(fan, 35)
    finally:
        for zone in sensors:
            inject(zone, 0)
    print(json.dumps(dict(phase='emulation', passed=True, sensors=SENSORS)))


def panel():
    fan, sensors = fan_device(), zones()
    original = [[int(p.read_text()) for p in trips(zone, fan)] for zone in sensors]
    assert all(table == original[0] for table in original)
    old = [original[0][i] // 1000 for i in (6, 10, 14)]
    config = Path('/etc/default/vim4-kvm-fan')
    saved = config.read_bytes() if config.exists() else None
    helper = '/usr/libexec/vim4-manager-helper'
    try:
        subprocess.run([helper, 'fan-curve', '65', '85', '100'], check=True)
        values = [[int(p.read_text()) for p in trips(zone, fan)] for zone in sensors]
        assert all(table == values[0] for table in values)
        assert [values[0][i] for i in (6, 10, 14)] == [65000, 85000, 100000]
        subprocess.run([helper, 'fan-restore'], check=True)
        assert all([int(p.read_text()) for p in trips(zone, fan)] == values[0] for zone in sensors)
    finally:
        subprocess.run([helper, 'fan-curve', *map(str, old)], check=True)
        if saved is None:
            config.unlink()
        else:
            config.write_bytes(saved)
    assert all([int(p.read_text()) for p in trips(zone, fan)] == original[0] for zone in sensors)
    print(json.dumps(dict(phase='panel-helper', passed=True)))


def read_thermal_state():
    state = snapshot()
    assert not state['sensor_fault'], state
    # Old quiet kernels expose only the maximum. Read all six independently.
    state['temperatures'] = {kind: int((zone / 'temp').read_text()) for kind, zone in zip(SENSORS, zones())}
    state['passive_states'] = {(p / 'type').read_text().strip(): int((p / 'cur_state').read_text())
                              for p in THERMAL.glob('cooling_device*')
                              if 'cpufreq' in (p / 'type').read_text()}
    state['cpu_policies'] = {p.name: {name: (p / name).read_text().strip() for name in
                                    ('scaling_governor', 'scaling_cur_freq', 'scaling_min_freq', 'scaling_max_freq')}
                             for p in Path('/sys/devices/system/cpu/cpufreq').glob('policy*')}
    return state


def sample(args):
    assert args.output and args.ambient is not None
    report = adaptive_sample(read_thermal_state,
                             progress=lambda window: print(json.dumps(window), flush=True))
    report.update(identity=running_identity(), role=args.role,
                  plan=json.loads(args.candidate_plan.read_text()), ambient=args.ambient,
                  stable=report['measurement'] is not None, workload=args.workload)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    assert report['stable'], 'No stable five-minute window within the 15-minute side limit'


def compare(args):
    baseline, candidate = [json.loads(p.read_text()) for p in (args.baseline, args.candidate)]
    assert baseline['role'] == 'baseline' and candidate['role'] == 'candidate'
    assert baseline['plan'] == candidate['plan'], 'Samples refer to different RAM candidates'
    measured = []
    for role, report in (('baseline', baseline), ('candidate', candidate)):
        verify_identity(report['plan'], role, report['identity'])
        window = select_measurement(report['readings'], report['started_monotonic'], report['elapsed'])
        assert window and window == report['measurement'], f'{role} is not a stable five-minute sample'
        selected = [r for r in report['readings'] if window['start_seconds'] <=
                    r['monotonic'] - report['started_monotonic'] < window['end_seconds']]
        measured.append(selected)
    assert baseline['workload'] == candidate['workload'], 'Use the same workload and settings'
    assert abs(baseline['ambient'] - candidate['ambient']) <= 1, 'Ambient temperatures differ by >1°C'
    def maximum(rows):
        return max(max(r['temperatures'].values()) for r in rows)
    old_rows, new_rows = measured
    assert maximum(new_rows) - maximum(old_rows) <= 3000, 'Maximum temperature increased >3°C'
    assert all(max(r['temperatures'][kind] for r in rows for kind in SENSORS[:2]) < 85000
               for rows in measured), 'CPU temperature is not below 85°C'
    def passive(rows):
        values = {}
        for reading in rows:
            for kind, state in reading['passive_states'].items():
                values[kind] = max(values.get(kind, 0), state)
        return values
    old = passive(old_rows)
    assert all(state <= old.get(kind, 0) for kind, state in passive(new_rows).items()), 'New CPU passive cooling'
    print(json.dumps(dict(phase='compare', passed=True, baseline_max=maximum(old_rows), candidate_max=maximum(new_rows),
                          baseline_window=baseline['measurement'], candidate_window=candidate['measurement'])))


def suspend():
    fan, sensors = fan_device(), zones()
    subprocess.run(['rtcwake', '-m', 'mem', '-s', '10'], check=True)
    deadline = time.monotonic() + 2
    while True:
        state = snapshot()
        assert not state['sensor_fault'], state
        target = max(max((duty for path, duty in zip(trips(zone, fan), DUTIES)
                          if int((zone / 'temp').read_text()) >= int(path.read_text())), default=0)
                     for zone in sensors)
        if int((fan / 'cur_state').read_text()) == target:
            break
        assert time.monotonic() < deadline, 'Resume fan state did not converge'
        time.sleep(.02)
    print(json.dumps(dict(phase='suspend', passed=True, state=state)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'emulation', 'panel', 'sample', 'compare', 'suspend'))
    parser.add_argument('--ram-package', type=Path, help='Externally built production RAM candidate.tar (prepare only)')
    parser.add_argument('--release', help='Expected release supplied by the integration builder')
    parser.add_argument('--sha256', help='Trusted RAM archive SHA256 supplied by the integration builder')
    parser.add_argument('--candidate-plan', type=Path, help='JSON produced by offline prepare')
    parser.add_argument('--role', choices=('baseline', 'candidate', 'returned'), default='candidate')
    parser.add_argument('--exclusive', action='store_true', help='Coordinator has reserved the board')
    parser.add_argument('--ambient', type=float)
    parser.add_argument('--workload', help='Exact source/application/codec/settings identity')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    if args.phase == 'prepare':
        if not all((args.ram_package, args.release, args.sha256, args.output)):
            parser.error('prepare requires --ram-package, --release, --sha256 and --output')
        prepare(args)
        return
    if args.phase == 'compare':
        assert args.baseline and args.candidate
        compare(args)
        return
    assert args.exclusive and os.geteuid() == 0, 'Requires root and a coordinated exclusive board window'
    assert args.candidate_plan, 'Provide the prepared external RAM candidate plan'
    verify_identity(json.loads(args.candidate_plan.read_text()), args.role, running_identity())
    assert args.phase == 'sample' or args.role == 'candidate', 'Control checks require the integration candidate'
    def interrupted(signum, frame):
        raise InterruptedError(f'Board check interrupted by signal {signum}')
    for signum in (signal.SIGTERM, signal.SIGALRM):
        signal.signal(signum, interrupted)
    signal.alarm(SIDE_SECONDS + 30 if args.phase == 'sample' else 900)
    if args.phase == 'sample':
        assert args.workload, 'Describe the already running workload'
        sample(args)
    else:
        {'emulation': emulation, 'panel': panel, 'suspend': suspend}[args.phase]()


if __name__ == '__main__':
    main()
