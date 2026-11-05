"""Read VIM4 cooling state and sensor health through thermal sysfs.

The private quiet-mode interface is retained only for older mainline kernels.
Control percentages are MCU values, not measured RPM.
"""
from pathlib import Path

SENSORS = ('a73-thermal', 'a53-thermal', 'gpu-thermal',
           'nna-thermal', 'vpu-thermal', 'hevc-thermal')


def snapshot(root=Path('/')):
    root = Path(root)
    thermal = root / 'sys/class/thermal'
    for device in thermal.glob('cooling_device*'):
        if (device / 'type').read_text().strip() == 'khadas-mcu-fan':
            maximum = int((device / 'max_state').read_text())
            speed = int((device / 'cur_state').read_text())
            if maximum != 100 or not 0 <= speed <= maximum:
                raise ValueError('Unexpected VIM4 fan cooling state')
            temperatures, errors = {}, {}
            for zone in thermal.glob('thermal_zone*'):
                kind = (zone / 'type').read_text().strip()
                if kind not in SENSORS:
                    continue
                try:
                    temperatures[kind] = int((zone / 'temp').read_text())
                    if (zone / 'mode').read_text().strip() != 'enabled':
                        errors[kind] = 'disabled'
                except OSError as error:
                    errors[kind] = str(error)
            for kind in SENSORS:
                if kind not in temperatures:
                    errors.setdefault(kind, 'missing or unreadable')
            return dict(speed_percent=speed, sensor_fault=int(bool(errors)),
                        temperature_millic=max(temperatures.values(), default=None),
                        temperatures=temperatures, sensor_errors=errors)
    legacy = root / 'sys/bus/platform/devices/khadas-mcu-fan-ctrl'
    return {name: int((legacy / name).read_text()) for name in
            ('speed_percent', 'sensor_fault', 'temperature_millic')}
