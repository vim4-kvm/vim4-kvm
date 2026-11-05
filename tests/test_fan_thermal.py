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
            rows = [dict(temperatures=dict.fromkeys(SENSORS, 50000), passive_states={'thermal-cpufreq-0': 0}) for _ in range(120)]
            baseline = dict(role='baseline', plan=plan, identity=plan['baseline'], elapsed=300, readings=rows, workload='same', ambient=25)
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
            for row in candidate['readings'][60:]:
                row['temperatures']['a73-thermal'] = 52000
            args.candidate.write_text(json.dumps(candidate))
            with self.assertRaisesRegex(AssertionError, 'stable five-minute'):
                check.compare(args)
            # A hot baseline that cooled before its last two minutes must not
            # inflate the comparison ceiling and hide a warmer candidate.
            cooling = copy.deepcopy(baseline)
            cooling['readings'] = copy.deepcopy(rows) + copy.deepcopy(rows)
            for row in cooling['readings'][:60]:
                row['temperatures']['a73-thermal'] = 60000
            self.assertFalse(check.steady(cooling['readings']))


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
