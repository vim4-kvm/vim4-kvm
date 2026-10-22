"""Persist confirmed boot contracts and repair missing USB data once at boot.

Only vim4-kvm-pd.service calls this entry point. Package installation must not
start/restart that service: an active USB link must survive runtime updates.
The manager imports the read-only decoders and previous-boot record reader.
Firmware snapshots and persisted contracts are history, never live PD state.
"""
import os
import json
import math
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
import struct
import subprocess

HANDOFF = Path('/proc/device-tree/chosen/khadas,usb-pd-boot')
ATTEMPT = Path('/run/vim4-kvm-pd-boot.done')
LAST_CONTRACT = Path('/var/lib/vim4-kvm/pd-last-contract.json')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')


def boot_power_contract(log):
    """Only completed bootstrap contracts; never infer consumption from PDOs."""
    if 'PD bootstrap complete; USB-capable 5V contract established' not in log:
        return None
    match = re.search(r'^PD contract at bootstrap: 5000mV (\d+)mA$', log, re.M)
    if match:
        current = int(match[1])
    else:
        # Older bootstrap logs only the first RDO. Later Source_Capabilities
        # can change the request without logging its value, so fail closed.
        if re.search(r'rx hdr [0-9a-f]+ data 1 n ', log):
            return None
        match = re.search(r'^Request rdo ([0-9a-f]{8}): tx 0$', log, re.M)
        if not match:
            return None
        rdo = int(match[1], 16)
        if rdo >> 28 != 1:
            return None
        current = ((rdo >> 10) & 0x3ff) * 10
    if not 0 < current <= 3000:
        return None
    return {'voltageV': 5, 'currentA': current / 1000}


def firmware_power(root=Path('/proc/device-tree/chosen')):
    """Decode the versioned U-Boot snapshot; never access the PD controller."""
    try:
        data = root.joinpath('khadas,usb-pd-boot').read_bytes()
    except OSError:
        return None
    if len(data) != 64:
        return None
    cells = [int.from_bytes(data[i:i + 4], 'big') for i in range(0, 64, 4)]
    version, flags, source, request, rdo, count, rp, policy_mv, policy_ma = cells[:9]
    if (version != 1 or flags & ~255 or count > 7 or rp > 3 or
            source > 0xffff or request > 0xffff or
            (count and (source & 31 != 1 or (source >> 12) & 7 != count))):
        return None
    pdos = []
    position = (rdo >> 28) & 7
    for index, raw in enumerate(cells[9:9 + count], 1):
        kind = raw >> 30
        pdo = {'position': index, 'raw': f'{raw:08x}',
               'type': ('Fixed', 'Battery', 'Variable', 'APDO')[kind]}
        if kind == 0:
            pdo.update(minVoltageV=((raw >> 10) & 1023) / 20,
                       maxVoltageV=((raw >> 10) & 1023) / 20,
                       maxCurrentA=(raw & 1023) / 100)
        elif kind in (1, 2):
            pdo.update(minVoltageV=((raw >> 10) & 1023) / 20,
                       maxVoltageV=((raw >> 20) & 1023) / 20)
            pdo['maxPowerW' if kind == 1 else 'maxCurrentA'] = (raw & 1023) / (4 if kind == 1 else 100)
        elif (raw >> 28) & 3 == 0:
            pdo.update(type='PPS', minVoltageV=((raw >> 8) & 255) / 10,
                       maxVoltageV=((raw >> 17) & 255) / 10, maxCurrentA=(raw & 127) / 20)
        pdos.append(pdo)
    # PS_RDY is evidence of completion. An I/O error makes the observed bytes
    # unreliable; policy targets and source ratings are never contract values.
    ps_ready = bool(flags & 1)
    selected = pdos[position - 1] if 0 < position <= count else None
    voltage = current = power = max_current = max_power = None
    request_valid = ((request >> 12) & 7 == 1 and request & 31 == 2 and
                     selected is not None)
    if request_valid:
        kind = selected['type']
        if kind in ('Fixed', 'Variable'):
            operating, maximum = ((rdo >> 10) & 1023) / 100, (rdo & 1023) / 100
            if 0 < operating <= maximum <= selected['maxCurrentA']:
                current = operating
                max_current = maximum
                if kind == 'Fixed':
                    voltage = selected['maxVoltageV'] or None
        elif kind == 'Battery':
            operating, maximum = ((rdo >> 10) & 1023) / 4, (rdo & 1023) / 4
            if 0 < operating <= maximum <= selected['maxPowerW']:
                power = operating
                max_power = maximum
        elif kind == 'PPS':
            mv, ma = ((rdo >> 9) & 4095) * 20, (rdo & 127) * 50
            if selected['minVoltageV'] * 1000 <= mv <= selected['maxVoltageV'] * 1000 and 0 < ma <= selected['maxCurrentA'] * 1000:
                voltage, current = mv / 1000, ma / 1000
                max_current = current
    contract = None
    if ps_ready and flags & 64 and not flags & (32 | 128) and voltage and current:
        contract = {'voltageV': voltage, 'currentA': max_current}
    revision = lambda header: ('1.0', '2.0', '3.0', 'unknown')[(header >> 6) & 3]
    return {'psReady': ps_ready, 'flags': flags, 'hardReset': bool(flags & 6),
            'requestFailed': bool(flags & 8), 'timedOut': bool(flags & 16),
            'ioError': bool(flags & 32), 'typecFallback': bool(flags & 128),
            'rp': ('unknown', 'default', '1.5A', '3A')[rp],
            'sourceRevision': revision(source) if count else None,
            'requestRevision': revision(request) if request else None,
            'sourceHeader': f'{source:04x}', 'requestHeader': f'{request:04x}',
            'rdo': f'{rdo:08x}', 'selectedPosition': position if selected else None,
            'selectedType': selected['type'] if selected else None,
            'requestedVoltageV': voltage, 'requestedCurrentA': current, 'requestedPowerW': power,
            'requestedMaxCurrentA': max_current, 'requestedMaxPowerW': max_power,
            'policyVoltageV': policy_mv / 1000, 'policyCurrentA': policy_ma / 1000,
            'contract': contract, 'sourceCapabilities': pdos}


def previous_contract(path=LAST_CONTRACT, boot_id=BOOT_ID):
    """Return a complete record from an earlier boot, without touching hardware."""
    try:
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            return None
        for key in ('voltageV', 'currentA'):
            value = record.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                return None
        if (type(record.get('usbComm')) is not bool or
                record.get('origin') not in ('linux', 'firmware') or
                not isinstance(record.get('rdo'), str) or
                not re.fullmatch(r'[0-9a-f]{8}', record['rdo']) or
                not isinstance(record.get('bootId'), str) or not record['bootId'] or
                type(record.get('establishedAt')) is not str or
                datetime.fromisoformat(record['establishedAt']).utcoffset() is None):
            return None
        return record if record['bootId'] != boot_id.read_text().strip() else None
    except (OSError, ValueError, TypeError):
        return None


def remember_contract(contract, rdo, origin, path=LAST_CONTRACT, boot_id=BOOT_ID):
    """Atomically publish confirmed boot history; failures must not retry PD."""
    temporary = None
    try:
        record = dict(contract, usbComm=bool(rdo & (1 << 25)), rdo=f'{rdo:08x}',
                      origin=origin, bootId=boot_id.read_text().strip(),
                      establishedAt=datetime.now().astimezone().isoformat(timespec='seconds'))
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(record, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as error:
        print(f'PD contract history unavailable: {error.strerror}', flush=True)
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def linux_bootstrap():
    # Capture only the existing tool output. Its protocol, arguments and exit
    # status remain unchanged; persistence failure never starts another attempt.
    result = subprocess.run(['/usr/sbin/usb-pd-init'], check=False,
                            stdout=subprocess.PIPE, text=True)
    print(result.stdout, end='', flush=True)
    contract = boot_power_contract(result.stdout)
    if result.returncode == 0 and contract:
        # request_5v uses these fixed bits and equal operating/maximum currents,
        # including later Source_Capabilities handled during the bootstrap.
        current = round(contract['currentA'] * 100)
        rdo = (1 << 28) | (1 << 25) | (1 << 24) | (current << 10) | current
        remember_contract(contract, rdo, 'linux')
    return result.returncode


def remember_firmware(handoff):
    firmware = firmware_power(handoff.parent)
    if firmware and firmware['contract']:
        remember_contract(firmware['contract'], int(firmware['rdo'], 16), 'firmware')


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
    remember_firmware(handoff)
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
    return linux_bootstrap()


if __name__ == '__main__':
    if sys.argv[1:] == ['--vendor']:
        remember_firmware(HANDOFF)
        raise SystemExit(linux_bootstrap())
    raise SystemExit(bootstrap())
