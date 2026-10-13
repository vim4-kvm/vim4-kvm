#!/usr/bin/python3
"""Regression test for HID epoll lifetime on a patched, exclusively held board.

Stop NanoKVM first. This disconnects USB repeatedly and must never run on the
old kernel: closing an epoll-registered HID fd after rebind can panic it.
"""
import argparse
import os
from pathlib import Path
import select
import subprocess
import time


def run(cycles):
    if os.geteuid() != 0:
        raise ValueError('Run as root on the patched board')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'nanokvm']).returncode == 0:
        raise ValueError('Stop NanoKVM and release the board before testing')
    udc = Path('/sys/kernel/config/usb_gadget/kvm/UDC')
    controller = udc.read_text().strip()
    if not controller:
        raise ValueError('Gadget must initially be bound')
    state = Path('/sys/class/udc') / controller / 'state'
    for cycle in range(cycles):
        files = []
        with select.epoll() as poll:
            try:
                for index in range(3):
                    fd = os.open(f'/dev/hidg{index}', os.O_RDWR | os.O_NONBLOCK)
                    files.append(fd)
                    poll.register(fd, select.EPOLLIN | select.EPOLLOUT)
                udc.write_text('\n')
                time.sleep(0.5)
                udc.write_text(controller)
                deadline = time.monotonic() + 15
                while state.read_text().strip() != 'configured':
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Host did not configure gadget after rebind')
                    time.sleep(0.1)
                # Both explicit DEL and close removal must survive. Do not
                # replace these with closing all descriptors before rebind.
                poll.unregister(files[0])
            finally:
                if not udc.read_text().strip():
                    udc.write_text(controller)
                for fd in files:
                    os.close(fd)
        print(f'PASS: rebind with live epoll descriptors {cycle + 1}/{cycles}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true')
    parser.add_argument('--fixed-kernel', action='store_true', help='Assert the fixed kernel was booted, not merely installed')
    parser.add_argument('--cycles', type=int, default=20)
    args = parser.parse_args()
    if not args.exclusive or not args.fixed_kernel or not 1 <= args.cycles <= 100:
        parser.error('Requires --exclusive --fixed-kernel and 1..100 cycles')
    run(args.cycles)
