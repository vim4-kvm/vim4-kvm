#!/usr/bin/env python3
"""Reject artifacts that can open HDMI capture before configuring its audio route."""
import configparser
from pathlib import Path
import shlex
import sys


def check(root):
    units = root / 'usr/lib/systemd/system'
    hdmi = configparser.ConfigParser(interpolation=None)
    hdmi.read(units / 'vim4-kvm-hdmi.service')
    app = configparser.ConfigParser(interpolation=None)
    app.read(units / 'nanokvm.service')
    for option in ('After', 'Wants'):
        if 'alsa-restore.service' not in hdmi.get('Unit', option, fallback='').split():
            raise ValueError(f'HDMI startup must order/pull ALSA restoration: missing {option}')
    route = shlex.split(hdmi.get('Service', 'ExecStartPre', fallback=''))
    if route != ['/usr/bin/amixer', '-q', '-D', 'hw:AMLAUGESOUND', 'cset',
                 'name=TDMIN_B source select', 'hdmirx']:
        raise ValueError('HDMI must configure its audio route in ExecStartPre')
    if 'vim4-kvm-hdmi.service' not in app.get('Unit', 'After', fallback='').split():
        raise ValueError('NanoKVM must start after HDMI initialization')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
    print('PASS: HDMI audio initialization precedes capture startup')
