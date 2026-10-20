"""Exclusive CRG trial: enumerate, send neutral HID reports, and rebind.

Run on the board as root with --exclusive; requires a 7.3 vim4kvm-crg test kernel.
With --storage-image, expose three HID interfaces and a read-only test disk.
The host must eject that disk and send 'continue' on stdin before each unbind.
This tool itself sends only neutral mouse reports; host input checks run separately.
"""
import argparse
import os
import select
from pathlib import Path
import platform
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exclusive', action='store_true', required=True)
parser.add_argument('--cycles', type=int, default=20)
parser.add_argument('--hold-seconds', type=float, default=1)
parser.add_argument('--keep-fd', action='store_true',
                    help='Keep a HID fd registered in epoll across each rebind')
parser.add_argument('--storage-image', type=Path,
                    help='Dedicated regular image file for the read-only composite trial')
args = parser.parse_args()
if os.geteuid() != 0 or not platform.release().startswith('7.3.0-rc7-vim4kvm-crg'):
    parser.error('Requires root on a 7.3 vim4kvm-crg trial kernel')
if not 1 <= args.cycles <= 100 or not 0 <= args.hold_seconds <= 120:
    parser.error('cycles must be 1..100 and hold-seconds 0..120')
if args.storage_image:
    if not args.storage_image.is_absolute() or not args.storage_image.is_file():
        parser.error('storage-image must be an absolute path to a regular image file')
    if args.storage_image.is_symlink() or args.storage_image.stat().st_size == 0:
        parser.error('storage-image must be nonempty and not a symlink')
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


def add_hid(name, protocol, subclass, length, descriptor):
    function = g / 'functions' / name
    function.mkdir()
    for attribute, value in [('protocol', protocol), ('subclass', subclass),
                             ('report_length', length), ('no_out_endpoint', 1)]:
        write(f'functions/{name}/{attribute}', value)
    (function / 'report_desc').write_bytes(bytes.fromhex(descriptor))
    (g / 'configs/c.1' / name).symlink_to(function)


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
    if args.storage_image:
        add_hid('hid.keyboard', 1, 1, 8,
                '05010906a101050719e029e715002501750195088102950175088101'
                '95057501050819012905910295017503910195067508150026ff00'
                '050719002aff008100c0')
        add_hid('hid.mouse_abs', 0, 0, 6,
                '05010902a1010901a10005091901290515002501950575018102950175038101'
                '0501093016000026ff7f751095018102093116000026ff7f751095018102'
                '09381581257f750895018106c0c0')
    add_hid('hid.mouse', 2, 1, 4,
        '05010902a1010901a10005091901290515002501950575018102950175038101'
        '0501093009311581257f75089502810609381581257f750895018106c0c0')
    if args.storage_image:
        (g / 'functions/mass_storage.disk').mkdir()
        write('functions/mass_storage.disk/lun.0/removable', 1)
        write('functions/mass_storage.disk/lun.0/ro', 1)
        write('functions/mass_storage.disk/lun.0/file', args.storage_image)
        (g / 'configs/c.1/mass_storage.disk').symlink_to(g / 'functions/mass_storage.disk')
    for cycle in range(args.cycles):
        if args.storage_image:
            # Host SCSI eject clears the backing path; reattach only while unbound.
            write('functions/mass_storage.disk/lun.0/file', args.storage_image)
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
        hid = os.open('/dev/hidg2' if args.storage_image else '/dev/hidg0',
                      os.O_WRONLY | os.O_NONBLOCK)
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
        if args.storage_image:
            print(f'cycle={cycle} host-ready; eject test disk then send continue', flush=True)
            if not select.select([sys.stdin], [], [], 120)[0]:
                raise TimeoutError('Host did not finish the composite checks within 120 seconds')
            if sys.stdin.readline().strip() != 'continue':
                raise RuntimeError('Host did not acknowledge test disk eject')
            backing = g / 'functions/mass_storage.disk/lun.0/file'
            if backing.read_text().strip():
                raise RuntimeError('Host must send SCSI eject before USB unbind')
        time.sleep(args.hold_seconds)
        write('UDC', '')
        print(f'cycle={cycle} unbound', flush=True)
        time.sleep(1)
finally:
    if held is not None:
        poller.unregister(held)
        os.close(held)
    poller.close()
    if (g / 'UDC').exists() and (g / 'UDC').read_text().strip():
        write('UDC', '')
    for link in (g / 'configs/c.1').glob('*'):
        if link.is_symlink():
            link.unlink()
    for function in (g / 'functions').iterdir():
        function.rmdir()
    for name in ['configs/c.1', 'strings/0x409']:
        if (g / name).exists():
            (g / name).rmdir()
    g.rmdir()
    print('Test gadget removed', flush=True)
