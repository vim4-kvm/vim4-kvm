#!/usr/bin/env python3
"""Local read-only 1Hz telemetry. Run only in the reserved benchmark window.

Missing sensors remain absent, never zero. Does not change clocks or power.
"""
import argparse
import errno
import glob
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

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


def receiver_state(backend):
    if backend == 'edge':
        sys.path.insert(0, '/usr/lib/vim4-kvm/python')
        from vim4video import capture_device, decode_timings, ioctl
        data = bytearray(132)
        with capture_device().open('rb', buffering=0) as device:
            try:
                ioctl(device.fileno(), 99, data, read_only=True)
            except OSError as error:
                if error.errno in (errno.ENOLINK, errno.ENODATA, errno.ERANGE):
                    return {'signal': False, 'errno': error.errno}
                raise
        return decode_timings(data)

    rx = Path('/sys/class/hdmirx/hdmirx0')
    def locked():
        return bool(int((rx / 'hw_info').read_text().strip(), 16) & (1 << 16))

    # Vendor info retains the last geometry after signal loss.
    if not locked():
        return {'signal': False}
    fields = dict(line.split(':', 1) for line in (rx / 'info').read_text().splitlines() if ':' in line)
    fields = {key.strip(): value.strip() for key, value in fields.items()}
    if not locked():
        return {'signal': False}
    width = int(fields['Hactive'])
    if fields['Color Space'].startswith('3-'):
        width *= 2
    return dict(signal=True, width=width, height=int(fields['Vactive']), interlaced=bool(int(fields['Interlace'])),
                refreshHz=int(fields['Frame Rate']) / 100)


def phase_state(backend):
    state = dict(hdmi=receiver_state(backend), wall_ns=time.time_ns())
    state['one_kvm'] = subprocess.check_output(
        ['systemctl', 'show', 'one-kvm', '-p', 'ActiveState', '--value'], text=True).strip()
    if state['one_kvm'] == 'active':
        with urllib.request.urlopen('http://127.0.0.1:8081/api/stream/status', timeout=3) as response:
            state['clients'] = json.load(response)['clients']
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-state', choices=('stock', 'edge'))
    parser.add_argument('--seconds', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--gpu-devfreq-only', action='store_true',
                        help='Avoid polling unrelated devfreq drivers in the video window')
    args = parser.parse_args()
    if args.phase_state:
        print(json.dumps(phase_state(args.phase_state)))
        return
    if args.seconds is None or not 1 <= args.seconds <= 7200 or args.output is None:
        parser.error('sampling requires --seconds 1..7200 and --output')
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
