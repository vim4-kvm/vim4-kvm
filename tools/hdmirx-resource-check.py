#!/usr/bin/env python3
"""Exclusive T7 receiver resource and failed-firmware trials; no video capture.

Run on the board's dedicated 7.3 vim4kvm-hdmirx test kernel as root. Each cycle
loads the receiver, checks clock rates and cable power, then unloads it while
holding an old debugfs fd. The driver must initially be unloaded.
Optional --reject-firmware names must refer to invalid or missing EDID fixtures.
"""
import argparse
import errno
import os
from pathlib import Path
import platform
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--expected-source-5v', type=int, choices=(0, 1), required=True)
    parser.add_argument('--reject-firmware', action='append', default=[],
                        help='EDID firmware name whose failed probe must release all resources')
    args = parser.parse_args()
    if os.geteuid() or not platform.release().startswith('7.3.0-rc7-vim4kvm-hdmirx'):
        parser.error('Requires root on the dedicated 7.3 HDMI receiver trial kernel')
    if not 1 <= args.cycles <= 20:
        parser.error('cycles must be 1..20')
    module = Path('/sys/module/t7_hdmirx')
    if module.exists():
        parser.error('Receiver is already loaded; refuse to interrupt its owner')
    status = Path('/sys/kernel/debug/fe398000.hdmi-receiver/status')
    clock_summary = Path('/sys/kernel/debug/clk/clk_summary')
    wanted = {'hdmirx_cfg', 'hdmirx_meter', 'hdmirx_2m', 'hdmirx_5m',
              't7_sys_hdmirx_pclk', 't7_sys_hdmirx'}
    held = None
    loaded = False

    def check_clock_references():
        clocks = {}
        for line in clock_summary.read_text().splitlines():
            fields = line.split()
            if fields and fields[0] in wanted:
                clocks[fields[0]] = [int(fields[1]), int(fields[2])]
        if clocks.keys() != wanted or any(counts != [0, 0] for counts in clocks.values()):
            raise RuntimeError(f'Clock references leaked after remove: {clocks}')
        return clocks

    try:
        for firmware in args.reject_firmware:
            subprocess.run(['modprobe', 't7-hdmirx', f'edid_firmware={firmware}'], check=True)
            loaded = True
            # Platform probe failure can leave the module loaded successfully.
            if status.exists() or Path('/sys/bus/platform/devices/fe398000.hdmi-receiver/driver').exists():
                raise RuntimeError(f'Invalid firmware unexpectedly published a receiver: {firmware}')
            subprocess.run(['modprobe', '-r', 't7-hdmirx'], check=True)
            loaded = False
            print(f'rejected firmware={firmware}; clock references={check_clock_references()}', flush=True)
        for cycle in range(args.cycles):
            subprocess.run(['modprobe', 't7-hdmirx'], check=True)
            loaded = True
            values = dict(line.split(': ', 1) for line in status.read_text().splitlines())
            print(f'cycle={cycle} status={values}', flush=True)
            if int(values['port']) != 1 or int(values['source_5v']) != args.expected_source_5v:
                raise RuntimeError('Receiver input port or source 5V differs from the fixture')
            for name, expected in [('cfg', 50000000), ('meter', 24000000),
                                   ('2m', 2000000), ('5m', 5000000)]:
                actual = int(values[f'{name}_hz'])
                if abs(actual - expected) > expected // 1000:
                    raise RuntimeError(f'{name} clock is {actual}, expected about {expected}')
            held = os.open(status, os.O_RDONLY)
            os.read(held, 4096)
            subprocess.run(['modprobe', '-r', 't7-hdmirx'], check=True)
            loaded = False
            if status.exists():
                raise RuntimeError('Receiver debugfs survived module unload')
            try:
                os.lseek(held, 0, os.SEEK_SET)
                os.read(held, 4096)
            except OSError as error:
                if error.errno not in (errno.EIO, errno.ENODEV, errno.ENOENT):
                    raise
            else:
                raise RuntimeError('Old debugfs fd remained readable after remove')
            os.close(held)
            held = None
            clocks = check_clock_references()
            print(f'cycle={cycle} removed; stale fd rejected; clock references={clocks}', flush=True)
        if Path('/proc/sys/kernel/tainted').read_text().strip() != '0':
            raise RuntimeError('Kernel became tainted; inspect dmesg')
        print(f'PASS: {args.cycles} receiver resource cycles; video capture not tested', flush=True)
    finally:
        if held is not None:
            os.close(held)
        if loaded:
            subprocess.run(['modprobe', '-r', 't7-hdmirx'], check=True)


if __name__ == '__main__':
    main()
