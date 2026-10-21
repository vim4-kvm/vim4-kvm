#!/usr/bin/env python3
"""Run on the board as root, with One-KVM stopped and virtual media ejected.

Exercises the candidate helper against configfs; restores the board profile
even when a check fails. Does not inject keyboard or mouse input into the host.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', default='/usr/libexec/vim4-onekvm')
    args = parser.parse_args()
    gadget = Path('/sys/kernel/config/usb_gadget/kvm')
    if (gadget / 'functions/mass_storage.disk0/lun.0/file').read_text().strip():
        raise RuntimeError('Safely eject and detach virtual media first')
    for service in ('one-kvm', 'one-kvm-edge'):
        if subprocess.run(['systemctl', 'is-active', '--quiet', service]).returncode == 0:
            raise RuntimeError(f'Stop {service} before changing USB functions')
    keys = ('idVendor', 'idProduct', 'strings/0x409/manufacturer',
            'strings/0x409/product', 'strings/0x409/serialnumber')
    descriptor = {key: (gadget / key).read_text().strip() for key in keys}
    original_links = sorted(p.name for p in (gadget / 'configs/c.1').iterdir() if p.is_symlink())
    profile = {'hid': dict(keyboard=True, mouse_absolute=True, mouse_relative=True, consumer=False),
               'descriptor': descriptor.copy(), 'network': '', 'uac': False,
               'inquiry': {'flash': 'One-KVM Test Disk', 'cdrom': 'One-KVM Test CD'}}
    profile['descriptor']['strings/0x409/product'] = 'One-KVM USB validation'

    def apply(label):
        subprocess.run(['python3', args.helper, 'usb', json.dumps(profile)], check=True)
        state_path = next(Path('/sys/class/udc').glob('*/state'))
        deadline = time.monotonic() + 10
        while (state := state_path.read_text().strip()) != 'configured' and time.monotonic() < deadline:
            time.sleep(0.1)
        links = sorted(p.name for p in (gadget / 'configs/c.1').iterdir() if p.is_symlink())
        print(json.dumps({'case': label, 'state': state, 'links': links}), flush=True)
        assert (gadget / 'strings/0x409/product').read_text().strip() == 'One-KVM USB validation'
        assert (gadget / 'UDC').read_text().strip()
        assert state == 'configured', state

    try:
        apply('three HID interfaces')
        profile['hid']['consumer'] = True
        apply('consumer control')
        assert Path('/dev/hidg3').exists()
        profile['hid']['consumer'] = False
        profile['hid']['keyboard'] = False
        profile['hid']['mouse_relative'] = False
        apply('absolute mouse only')
        assert not (gadget / 'configs/c.1/hid.keyboard').exists()
        assert (gadget / 'functions/hid.keyboard').is_dir()
        assert Path('/dev/hidg1').exists()  # the absolute mouse retains its number
        profile['hid']['keyboard'] = True
        profile['hid']['mouse_relative'] = True
        profile['uac'] = True
        apply('UAC2 microphone')
        print(Path('/proc/asound/cards').read_text(), flush=True)
        profile['uac'] = False
        for mode in ('ncm', 'ecm', 'rndis'):
            profile['network'] = mode
            apply(mode)
            interface = (gadget / f'functions/{mode}.usb0/ifname').read_text().strip()
            result = subprocess.check_output(['ip', '-j', 'address', 'show', 'dev', interface], text=True)
            assert any(address['family'] == 'inet' for device in json.loads(result) for address in device['addr_info'])
            print(result, flush=True)
        profile['hid']['consumer'] = True
        result = subprocess.run(['python3', args.helper, 'usb', json.dumps(profile)], capture_output=True, text=True)
        assert result.returncode != 0 and 'endpoint limit' in result.stderr
        print('Endpoint overflow rejected without losing the working profile', flush=True)
    finally:
        subprocess.run(['python3', args.helper, 'usb-restore'], check=True)
        assert {key: (gadget / key).read_text().strip() for key in keys} == descriptor
        assert sorted(p.name for p in (gadget / 'configs/c.1').iterdir() if p.is_symlink()) == original_links
        print('Original board USB profile restored', flush=True)


if __name__ == '__main__':
    main()
