#!/usr/bin/env python3
"""Sample VIM4 RX port 1 control state on the board as root.

Writes only register-read commands to the driver's debug interface. Does not
reset HDMI, change EDID, or clear the kernel log. Output is JSON lines; these
are register snapshots, not a DDC transaction/ACK trace.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time


DEBUG = Path('/sys/class/hdmirx/hdmirx0/debug')
# Fixed read commands from rx_debug_rd_reg; the last argument selects RX port 1.
# Avoid interrupt and error-counter registers whose read side effects are unclear.
READS = ('rhd301 1', 'rhd302 1', 'rhd320 1', 'rhd321 1', 'rhd340 1', 'rht25 1')
REGISTER = re.compile(r'\[RX\]-(?:DWC|TOP) \[[0-9a-f]+\]=[0-9a-f]+')


def drain(fd):
    records = []
    while True:
        try:
            raw = os.read(fd, 65536)
        except BlockingIOError:
            return records
        except OSError as error:
            # /dev/kmsg reports EPIPE if records were overwritten: do not hide it.
            raise RuntimeError('kernel log read failed; sample is incomplete') from error
        if not raw:
            return records
        message = raw.decode(errors='replace')
        if REGISTER.search(message):
            records.append(message.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error('--seconds must be 1..600')
    if os.geteuid() != 0:
        parser.error('run on the VIM4 as root')
    fd = os.open('/dev/kmsg', os.O_RDONLY | os.O_NONBLOCK)
    try:
        os.lseek(fd, 0, os.SEEK_END)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            started = time.monotonic()
            for command in READS:
                DEBUG.write_text(command + '\n')
            capture = {}
            for device in Path('/sys/class/video4linux').glob('video*'):
                if (device / 'name').read_text().strip() == 'vfm_cap':
                    for name in ('status', 'stats'):
                        capture[name] = (device / name).read_text()
            print(json.dumps({'time_ns': time.time_ns(),
                              'registers': drain(fd), 'capture': capture}), flush=True)
            time.sleep(max(0, min(1 - (time.monotonic() - started),
                                 deadline - time.monotonic())))
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
