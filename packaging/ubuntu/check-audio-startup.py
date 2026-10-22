#!/usr/bin/env python3
"""Reject artifacts that can open HDMI capture before configuring its audio route."""
import configparser
from pathlib import Path
import shlex
import sys


def check(root):
    units = root / 'usr/lib/systemd/system'
    # EnvironmentFile is repeatable in systemd. The audio route remains checked
    # below; unrelated repeated settings must not reject an otherwise valid unit.
    hdmi = configparser.ConfigParser(interpolation=None, strict=False)
    hdmi.read(units / 'vim4-kvm-hdmi.service')
    # systemd allows repeated options such as ExecStartPre; only [Unit] is read.
    app = configparser.ConfigParser(interpolation=None, strict=False)
    app.read(units / 'nanokvm.service')
    for option in ('After', 'Wants'):
        if 'alsa-restore.service' not in hdmi.get('Unit', option, fallback='').split():
            raise ValueError(f'HDMI startup must order/pull ALSA restoration: missing {option}')
    route = shlex.split(hdmi.get('Service', 'ExecStartPre', fallback=''))
    legacy = ['/usr/bin/amixer', '-q', '-D', 'hw:AMLAUGESOUND', 'cset',
              'name=TDMIN_B source select', 'hdmirx']
    dual_kernel = ['/usr/libexec/vim4-board-runtime', 'audio-route']
    if route == dual_kernel:
        wrapper = root / 'usr/libexec/vim4-board-runtime'
        if not wrapper.is_file() or not wrapper.stat().st_mode & 0o111:
            raise ValueError('HDMI kernel dispatcher is missing or not executable')
        if hdmi.get('Service', 'Type', fallback='') != 'notify':
            raise ValueError('HDMI must report readiness after mainline audio initialization')
    elif route != legacy:
        raise ValueError('HDMI must configure its audio route in ExecStartPre')
    if 'vim4-kvm-hdmi.service' not in app.get('Unit', 'After', fallback='').split():
        raise ValueError('NanoKVM must start after HDMI initialization')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
    print('PASS: HDMI audio initialization precedes capture startup')
