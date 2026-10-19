"""Exclusive CRG trial: enumerate, send neutral HID reports, and rebind.

Run on the board as root with --exclusive; requires a 7.3 vim4kvm-crg test kernel.
No cursor movement, keyboard input or virtual storage is generated.
"""
import argparse
import os
import select
from pathlib import Path
import platform
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exclusive', action='store_true', required=True)
parser.add_argument('--cycles', type=int, default=20)
parser.add_argument('--hold-seconds', type=float, default=1)
parser.add_argument('--keep-fd', action='store_true',
                    help='Keep a HID fd registered in epoll across each rebind')
args = parser.parse_args()
if os.geteuid() != 0 or not platform.release().startswith('7.3.0-rc7-vim4kvm-crg'):
    parser.error('Requires root on a 7.3 vim4kvm-crg trial kernel')
if not 1 <= args.cycles <= 100 or not 0 <= args.hold_seconds <= 120:
    parser.error('cycles must be 1..100 and hold-seconds 0..120')
root = Path('/sys/kernel/config/usb_gadget')
if not root.is_dir() or list(root.iterdir()):
    raise SystemExit('Requires mounted configfs with no existing gadgets')
controllers = list(Path('/sys/class/udc').iterdir())
if len(controllers) != 1:
    raise SystemExit(f'Expected one UDC, found {controllers}')
udc = controllers[0]
g = root / 'crg-test'
g.mkdir()
held = None
poller = select.epoll()


def write(name, value):
    # An empty write does not invoke the configfs store callback; unbind needs a newline.
    (g / name).write_text(str(value) + '\n')


try:
    write('idVendor', '0x1d6b')
    write('idProduct', '0x0104')
    write('bcdDevice', '0x0100')
    write('bcdUSB', '0x0200')
    (g / 'strings/0x409').mkdir()
    write('strings/0x409/serialnumber', 'VIM4-CRG-TEST')
    write('strings/0x409/manufacturer', 'vim4-kvm')
    write('strings/0x409/product', 'VIM4 CRG Test')
    (g / 'configs/c.1').mkdir()
    write('configs/c.1/MaxPower', 250)
    f = g / 'functions/hid.mouse'
    f.mkdir()
    write('functions/hid.mouse/protocol', 2)
    write('functions/hid.mouse/subclass', 1)
    write('functions/hid.mouse/report_length', 4)
    write('functions/hid.mouse/no_out_endpoint', 1)
    (f / 'report_desc').write_bytes(bytes.fromhex(
        '05010902a1010901a10005091901290515002501950575018102950175038101'
        '0501093009311581257f75089502810609381581257f750895018106c0c0'))
    (g / 'configs/c.1/hid.mouse').symlink_to(f)
    for cycle in range(args.cycles):
        write('UDC', udc.name)
        deadline = time.monotonic() + 20
        previous = None
        while True:
            state = (udc / 'state').read_text().strip()
            if state != previous:
                print(f'cycle={cycle} state={state}', flush=True)
                previous = state
            if state == 'configured':
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Enumeration timed out: {state}')
            time.sleep(.2)
        hid = os.open('/dev/hidg0', os.O_WRONLY | os.O_NONBLOCK)
        try:
            # Repeated writes prove previous requests complete, not just one queued buffer.
            for report in range(10):
                deadline = time.monotonic() + 3
                while True:
                    try:
                        written = os.write(hid, bytes(4))
                        if written != 4:
                            raise OSError(f'Short HID write: {written}')
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Previous HID report did not complete')
                        time.sleep(.02)
                time.sleep(.1)
            if held is not None:
                poller.unregister(held)
                os.close(held)
                held = None
            if args.keep_fd:
                poller.register(hid, select.EPOLLIN | select.EPOLLOUT)
                held = hid
        finally:
            if hid != held:
                os.close(hid)
        print(f'cycle={cycle} 10 neutral HID reports submitted', flush=True)
        time.sleep(args.hold_seconds)
        write('UDC', '')
        print(f'cycle={cycle} unbound', flush=True)
        time.sleep(1)
finally:
    if held is not None:
        poller.unregister(held)
        os.close(held)
    poller.close()
    if (g / 'UDC').read_text().strip():
        write('UDC', '')
    link = g / 'configs/c.1/hid.mouse'
    if link.is_symlink():
        link.unlink()
    for name in ['functions/hid.mouse', 'configs/c.1', 'strings/0x409']:
        if (g / name).exists():
            (g / name).rmdir()
    g.rmdir()
    print('Test gadget removed', flush=True)
