#!/usr/bin/env python3
"""Local read-only 1Hz telemetry. Run only in the reserved benchmark window.

Missing sensors remain absent, never zero. Does not change clocks or power.
"""
import argparse
import glob
import json
from pathlib import Path
import time

PATTERNS = (
    '/sys/class/thermal/thermal_zone*/type', '/sys/class/thermal/thermal_zone*/temp',
    '/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq',
    '/sys/devices/system/cpu/cpufreq/policy*/related_cpus',
    '/sys/devices/system/cpu/cpufreq/policy*/stats/time_in_state',
    '/sys/devices/system/cpu/cpu*/cpuidle/state*/name',
    '/sys/devices/system/cpu/cpu*/cpuidle/state*/usage',
    '/sys/devices/system/cpu/cpu*/cpuidle/state*/time',
    '/sys/class/thermal/cooling_device*/type', '/sys/class/thermal/cooling_device*/cur_state',
    '/sys/bus/platform/devices/khadas-mcu-fan-ctrl/speed_percent', '/sys/class/fan/speed',
    '/sys/devices/system/cpu/cpufreq/policy*/scaling_governor',
    '/sys/devices/system/cpu/cpufreq/policy*/scaling_available_frequencies',
    '/sys/class/mpgpu/cur_freq',
    '/sys/class/devfreq/*/cur_freq', '/sys/class/devfreq/*/governor',
    '/sys/class/devfreq/*/available_frequencies', '/sys/class/devfreq/*/device/power/runtime_status',
    '/sys/class/hwmon/hwmon*/name', '/sys/class/hwmon/hwmon*/power*_input',
    '/sys/class/hwmon/hwmon*/power*_label', '/sys/class/hwmon/hwmon*/energy*_input',
    '/proc/loadavg', '/proc/stat', '/proc/meminfo', '/proc/sys/kernel/tainted',
)


def snapshot(names=None):
    values, errors = {}, {}
    for name in names if names is not None else sensor_paths():
        try:
            values[name] = Path(name).read_text().strip()
        except OSError as error:
            errors[name] = str(error)
    return dict(monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns(), values=values, errors=errors)


def sensor_paths():
    return [name for pattern in PATTERNS for name in glob.glob(pattern)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--gpu-devfreq-only', action='store_true',
                        help='Avoid polling unrelated devfreq drivers in the video window')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 7200:
        parser.error('seconds must be 1..7200')
    with args.output.open('x') as output:
        names = sensor_paths()
        if args.gpu_devfreq_only:
            names = [name for name in names if not name.startswith('/sys/class/devfreq/')
                     or name.startswith('/sys/class/devfreq/fe400000.gpu/')]
        for _ in range(args.seconds):
            start = time.monotonic()
            output.write(json.dumps(snapshot(names)) + '\n')
            output.flush()
            time.sleep(max(0, start + 1 - time.monotonic()))


if __name__ == '__main__':
    main()
