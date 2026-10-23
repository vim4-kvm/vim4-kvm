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
    '/sys/devices/system/cpu/cpufreq/policy*/*cur_freq',
    '/sys/devices/system/cpu/cpufreq/policy*/scaling_governor',
    '/sys/devices/system/cpu/cpufreq/policy*/scaling_available_frequencies',
    '/sys/class/devfreq/*/cur_freq', '/sys/class/devfreq/*/governor',
    '/sys/class/devfreq/*/available_frequencies', '/sys/class/devfreq/*/device/power/runtime_status',
    '/sys/class/hwmon/hwmon*/name', '/sys/class/hwmon/hwmon*/power*_input',
    '/sys/class/hwmon/hwmon*/power*_label', '/sys/class/hwmon/hwmon*/energy*_input',
    '/proc/loadavg', '/proc/stat', '/proc/sys/kernel/tainted',
)


def snapshot():
    values, errors = {}, {}
    for pattern in PATTERNS:
        for name in glob.glob(pattern):
            try:
                values[name] = Path(name).read_text().strip()
            except OSError as error:
                errors[name] = str(error)
    return dict(monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns(), values=values, errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 7200:
        parser.error('seconds must be 1..7200')
    with args.output.open('x') as output:
        start = time.monotonic()
        for index in range(args.seconds):
            time.sleep(max(0, start + index - time.monotonic()))
            output.write(json.dumps(snapshot()) + '\n')
            output.flush()


if __name__ == '__main__':
    main()
