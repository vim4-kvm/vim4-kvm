"""Thermal numbering and partial sensor availability are observable contracts."""
import sys
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'board'))
from vim4fan import snapshot, SENSORS

SPEC = importlib.util.spec_from_file_location('fan_check', Path(__file__).resolve().parents[1] / 'tools/fan-thermal-check.py')
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def replay(temperature):
    """Drive the actual sampling loop with a clock, never wait for wall time."""
    now = [0.0]
    def sleep(seconds):
        now[0] += seconds
    def read():
        values = temperature(now[0])
        if isinstance(values, int):
            values = dict.fromkeys(SENSORS, values)
        return dict(temperatures=values, passive_states={'cpufreq-cpu0': 0})
    return check.adaptive_sample(read, clock=lambda: now[0], sleep=sleep)


class AdaptiveTemperatureTest(unittest.TestCase):
    def test_warming_and_cooling_settle_on_the_same_first_complete_window(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                report = replay(lambda t: int(50000 + direction * max(0, 360 - t) * 20))
                self.assertEqual(report['measurement']['start_seconds'], 360)
                self.assertEqual(report['measurement']['end_seconds'], 660)
                self.assertEqual(report['elapsed'], 660)
                self.assertEqual(len(report['readings']), 660)  # early drift retained
                self.assertFalse(report['checks'][0]['stable'])

    def test_all_six_zones_must_settle_and_drift_stops_at_fifteen_minutes(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                def values(t):
                    temperatures = dict.fromkeys(SENSORS, 50000)
                    temperatures[SENSORS[-1]] += int(direction * t * 20)
                    return temperatures
                report = replay(values)
                self.assertIsNone(report['measurement'])
                self.assertEqual(report['elapsed'], 900)
                self.assertFalse(any(c['stable'] for c in report['checks']))

    def test_inclusive_half_degree_boundary_and_last_permitted_window(self):
        for spread, accepted in ((500, True), (501, False)):
            with self.subTest(spread=spread):
                report = replay(lambda t: 50000 + (spread if int(t // 60) % 2 else 0))
                self.assertEqual(report['measurement'] is not None, accepted)
                if accepted:
                    self.assertEqual(report['elapsed'], 480)
        report = replay(lambda t: int(50000 + max(0, 600 - t) * 20))
        self.assertEqual(report['measurement']['end_seconds'], 900)

    def test_time_buckets_do_not_treat_a_partial_minute_as_complete(self):
        rows = [dict(monotonic=t, temperatures=dict.fromkeys(SENSORS, 50000))
                for t in range(180, 480)]
        self.assertIsNone(check.select_measurement(rows, 0, 479.99))
        self.assertTrue(check.select_measurement(rows, 0, 480)['stable'])
        # Five minutes are required even if an oversampled four-minute tail
        # has enough rows to look like five groups of sixty samples.
        incomplete = [dict(monotonic=240 + i / 2, temperatures=dict.fromkeys(SENSORS, 50000))
                      for i in range(480)]
        self.assertIsNone(check.select_measurement(incomplete, 0, 480))


class FanCandidateTest(unittest.TestCase):
    def test_external_archive_identity_and_tampering(self):
        from test_display_once import TrialTest, once
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = '7.3.1-vim4-20261105.99'
            formal = once.formal_baseline()
            TrialTest().fixture(root, release=release, baseline_release=formal['release'])
            state = json.loads((root / 'baseline.json').read_text())
            state['build_id'] = formal['build_id']
            (root / 'baseline.json').write_text(json.dumps(state))
            once.prepare(root / 'payload', root / 'init', root / 'baseline.json', root / 'external', release=release)
            bundle = root / 'external/candidate.tar'
            args = SimpleNamespace(ram_package=bundle, sha256=once.sha(bundle), release=release, output=root / 'plans/fan-plan.json')
            check.prepare(args)
            plan = json.loads(args.output.read_text())
            self.assertEqual(plan['candidate']['build_id'], '1' * 40)
            self.assertEqual(plan['baseline']['build_id'], formal['build_id'])
            args.release = '7.3.1-vim4-20261105.98'
            with self.assertRaisesRegex(ValueError, 'release differs'):
                check.prepare(args)
            args.release = release
            bundle.write_bytes(bundle.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                check.prepare(args)

    def test_compare_rejects_wrong_kernel_and_unsettled_temperature(self):
        import copy
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = dict(baseline=dict(release='baseline', build_id='a'), candidate=dict(release='candidate', build_id='b'))
            baseline = replay(lambda t: 60000 if t < 180 else 50000)
            baseline.update(role='baseline', plan=plan, identity=plan['baseline'], workload='same', ambient=25)
            candidate = copy.deepcopy(baseline)
            candidate.update(role='candidate', identity=plan['candidate'])
            args = SimpleNamespace(baseline=root / 'base.json', candidate=root / 'candidate.json')
            args.baseline.write_text(json.dumps(baseline))
            args.candidate.write_text(json.dumps(candidate))
            check.compare(args)
            candidate['identity'] = dict(release='unexpected', build_id='b')
            args.candidate.write_text(json.dumps(candidate))
            with self.assertRaisesRegex(ValueError, 'release/build ID'):
                check.compare(args)
            candidate['identity'] = plan['candidate']
            for row in candidate['readings'][240:]:
                row['temperatures']['a73-thermal'] = 52000
            args.candidate.write_text(json.dumps(candidate))
            with self.assertRaisesRegex(AssertionError, 'stable five-minute'):
                check.compare(args)
            # A hot baseline that cooled before its last two minutes must not
            # inflate the comparison ceiling and hide a warmer candidate.
            cooling = replay(lambda t: 60000 if t < 360 else 50000)
            self.assertIsNone(check.select_measurement(cooling['readings'], 0, 480))

    def test_compare_uses_selected_window_and_keeps_three_degree_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = dict(baseline=dict(release='baseline', build_id='a'), candidate=dict(release='candidate', build_id='b'))
            args = SimpleNamespace(baseline=root / 'base.json', candidate=root / 'candidate.json')
            for temperature, accepted in ((53000, True), (53001, False)):
                baseline = replay(lambda t: 60000 if t < 180 else 50000)
                candidate = replay(lambda t: temperature)
                for role, report, path in (('baseline', baseline, args.baseline), ('candidate', candidate, args.candidate)):
                    report.update(role=role, identity=plan[role], plan=plan, workload='same', ambient=29)
                    path.write_text(json.dumps(report))
                if accepted:
                    check.compare(args)
                else:
                    with self.assertRaisesRegex(AssertionError, 'increased >3'):
                        check.compare(args)


class FanThermalTest(unittest.TestCase):
    def test_numbering_missing_sensor_and_disabled_zone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thermal = root / 'sys/class/thermal'
            fan = thermal / 'cooling_device17'
            fan.mkdir(parents=True)
            for key, value in dict(type='khadas-mcu-fan', max_state='100', cur_state='70').items():
                (fan / key).write_text(value)
            for i, kind in enumerate(SENSORS):
                zone = thermal / f'thermal_zone{i + 8}'
                zone.mkdir()
                for key, value in dict(type=kind, temp=str(40000 + i * 1000), mode='enabled').items():
                    (zone / key).write_text(value)
            self.assertEqual(snapshot(root)['temperature_millic'], 45000)
            self.assertEqual(snapshot(root)['sensor_fault'], 0)
            (thermal / 'thermal_zone13/temp').unlink()
            (thermal / 'thermal_zone8/mode').write_text('disabled')
            result = snapshot(root)
            self.assertEqual(result['speed_percent'], 70)
            self.assertEqual(result['temperature_millic'], 44000)
            self.assertEqual(set(result['sensor_errors']), {SENSORS[0], SENSORS[5]})

    def test_old_quiet_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / 'sys/bus/platform/devices/khadas-mcu-fan-ctrl'
            legacy.mkdir(parents=True)
            for key, value in dict(speed_percent=15, sensor_fault=0, temperature_millic=50000).items():
                (legacy / key).write_text(str(value))
            self.assertEqual(snapshot(directory)['speed_percent'], 15)
