#!/usr/bin/env python3
"""Print a RAM-only U-Boot command using the recorded baseline board MAC."""
import re
import sys


def command(mac, build_id):
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac):
        raise ValueError('Expected a baseline Ethernet MAC address')
    octets = bytes.fromhex(mac.replace(':', ''))
    if octets[0] & 1 or octets == bytes(6):
        raise ValueError('Expected a nonzero unicast MAC')
    if not re.fullmatch(r'[0-9a-f]{40}', build_id):
        raise ValueError('Expected a 40-digit build ID')
    path = f'/var/lib/vim4-kvm/hdr2-unified/{build_id}/extlinux.conf'
    return f'setenv ethaddr {mac.lower()}; sysboot mmc 1:2 any ${{pxefile_addr_r}} {path}; reset'


if __name__ == '__main__':
    print(command(*sys.argv[1:]))
