#!/usr/bin/python3
"""Apply the board's U-Boot/eFuse MAC before udev and NetworkManager start.

The vendor boot path uses eth_mac, whereas U-Boot's separate ethaddr may be a
locally administered fallback. No board identity is stored in this program.
"""
from pathlib import Path
import re
import sys


def generate(cmdline, directory):
    words=cmdline.split()
    if 'vim4.full_kvm=1' not in words:return
    values=[w.split('=',1)[1] for w in words if w.startswith('vim4.eth_mac=')]
    if len(values)!=1 or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',values[0]):
        raise ValueError('Expected one factory MAC from U-Boot eth_mac')
    mac=values[0].lower()
    data=bytes.fromhex(mac.replace(':',''))
    if data==bytes(6) or data[0]&1:raise ValueError('Factory MAC must be a nonzero unicast address')
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'10-vim4-ethernet.link').write_text(
        '# Generated from U-Boot factory identity; do not persist this file.\n'
        '[Match]\nPath=platform-fdc00000.ethernet\n\n'
        '[Link]\nMACAddressPolicy=none\nMACAddress='+mac+'\n')


if __name__=='__main__':
    try:generate(Path('/proc/cmdline').read_text(),Path('/run/systemd/network'))
    except ValueError as error:
        print('vim4-ethernet-generator: '+str(error),file=sys.stderr)
        sys.exit(1)
