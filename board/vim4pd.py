"""Repair a confirmed firmware PD contract without USB data, once at boot.

Only vim4-kvm-pd.service calls this entry point. Package installation must not
start/restart that service: an active USB link must survive runtime updates.
The firmware snapshot is historical; it is never polled as current PD state.
"""
import os
from pathlib import Path
import struct
import subprocess

HANDOFF = Path('/proc/device-tree/chosen/khadas,usb-pd-boot')
ATTEMPT = Path('/run/vim4-kvm-pd-boot.done')


def decision(data):
    """Return whether a version-1 firmware snapshot needs USB negotiation."""
    if len(data) != 64:
        return False, 'invalid firmware snapshot length'
    cells = struct.unpack('>16I', data)
    version, flags = cells[:2]
    if version != 1:
        return False, 'unsupported firmware snapshot version'
    if flags & ((1 << 4) | (1 << 7)):
        return False, 'firmware timeout or Type-C fallback'
    if not flags & 1:
        return False, 'firmware has no PS_RDY-completed contract'
    if flags & (1 << 5):
        return False, 'firmware controller I/O error'
    rdo, count = cells[4:6]
    position = (rdo >> 28) & 7
    if not 1 <= position <= count <= 7:
        return False, 'invalid firmware Request position or PDO count'
    if rdo & (1 << 25):
        return False, 'firmware Request already has USB Communications Capable'
    return True, 'PS_RDY contract lacks USB Communications Capable; requesting USB-capable 5V'


def bootstrap(handoff=HANDOFF, attempt=ATTEMPT):
    # Claim before reading or negotiating, including failures. A service restart
    # in this boot must never replay the old snapshot or retry an active link.
    try:
        fd = os.open(attempt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('PD bootstrap skipped: already considered this boot', flush=True)
        return 0
    os.close(fd)
    try:
        negotiate, reason = decision(handoff.read_bytes())
    except FileNotFoundError:
        negotiate, reason = False, 'firmware snapshot missing'
    except OSError:
        negotiate, reason = False, 'firmware snapshot unreadable'
    print('PD bootstrap ' + ('repair: ' if negotiate else 'skipped: ') + reason, flush=True)
    if not negotiate:
        return 0
    # The service timeout bounds this single attempt; failure is visible and
    # deliberately does not schedule another negotiation.
    return subprocess.run(['/usr/sbin/usb-pd-init'], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(bootstrap())
