"""Thermal numbering and partial sensor availability are observable contracts."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'board'))
from vim4fan import snapshot, SENSORS


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
