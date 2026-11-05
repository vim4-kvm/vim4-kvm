#!/usr/bin/env python3
"""Prepared board-window checks; never acquires a board window itself.

Run only after the coordinator reserves the board. sample observes an already
running, preheated workload. compare is offline. Other phases change thermal
emulation, fan settings or system sleep and restore their temporary settings.
"""
import argparse
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, '/usr/lib/vim4-kvm/python')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'board'))
from vim4fan import SENSORS, snapshot

THERMAL = Path('/sys/class/thermal')
DUTIES = (5, 10, 15, 20, 25, 30, 35, 43, 52, 61, 70, 77, 85, 92, 100)


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


def sample(args):
    assert args.output and args.ambient is not None
    assert 10 <= args.seconds <= 600
    readings = []
    start = time.monotonic()
    while time.monotonic() - start < args.seconds:
        state = snapshot()
        assert not state['sensor_fault'], state
        # Old quiet kernels expose only the maximum, so collect six temperatures
        # independently for comparable CPU and per-sensor evidence.
        state['temperatures'] = {kind: int((zone / 'temp').read_text()) for kind, zone in zip(SENSORS, zones())}
        state['passive_states'] = {(p / 'type').read_text().strip(): int((p / 'cur_state').read_text())
                                   for p in THERMAL.glob('cooling_device*')
                                   if 'cpufreq' in (p / 'type').read_text()}
        state['monotonic'] = time.monotonic()
        readings.append(state)
        time.sleep(1)
    args.output.write_text(json.dumps(dict(kernel=os.uname().release, ambient=args.ambient,
                                          workload=args.workload, readings=readings), indent=2) + '\n')


def compare(args):
    baseline, candidate = [json.loads(p.read_text()) for p in (args.baseline, args.candidate)]
    assert baseline['workload'] == candidate['workload'], 'Use the same workload and settings'
    assert abs(baseline['ambient'] - candidate['ambient']) <= 1, 'Ambient temperatures differ by >1°C'
    def maximum(report):
        return max(max(r['temperatures'].values()) for r in report['readings'])
    assert maximum(candidate) - maximum(baseline) <= 3000, 'Maximum temperature increased >3°C'
    assert max(r['temperatures'][kind] for r in candidate['readings'] for kind in SENSORS[:2]) < 85000
    def passive(report):
        values = {}
        for reading in report['readings']:
            for kind, state in reading['passive_states'].items():
                values[kind] = max(values.get(kind, 0), state)
        return values
    old = passive(baseline)
    assert all(state <= old.get(kind, 0) for kind, state in passive(candidate).items()), 'New CPU passive cooling'
    print(json.dumps(dict(phase='compare', passed=True, baseline_max=maximum(baseline), candidate_max=maximum(candidate))))


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
    parser.add_argument('phase', choices=('emulation', 'panel', 'sample', 'compare', 'suspend'))
    parser.add_argument('--exclusive', action='store_true', help='Coordinator has reserved the board')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--ambient', type=float)
    parser.add_argument('--workload', help='Exact source/application/codec/settings identity')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    if args.phase == 'compare':
        assert args.baseline and args.candidate
        compare(args)
        return
    assert args.exclusive and os.geteuid() == 0, 'Requires root and a coordinated exclusive board window'
    def interrupted(signum, frame):
        raise InterruptedError(f'Board check interrupted by signal {signum}')
    for signum in (signal.SIGTERM, signal.SIGALRM):
        signal.signal(signum, interrupted)
    signal.alarm(900)
    if args.phase == 'sample':
        assert args.workload, 'Describe the already running preheated workload'
        sample(args)
    else:
        {'emulation': emulation, 'panel': panel, 'suspend': suspend}[args.phase]()


if __name__ == '__main__':
    main()
