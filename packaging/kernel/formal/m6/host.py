#!/usr/bin/env python3
"""M6-only native receivers. No HID is injected by this program."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

brand = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
hostname = subprocess.check_output(['hostname'], text=True).strip()
assert hostname.split('.')[0].lower() == 'deepdremsminim6', 'Refusing the M6 fixture on another Mac: ' + hostname
root = Path(__file__).resolve().parent
command = sys.argv[1]
volume = Path('/Volumes/EDGEUSB21')
marker = 'VIM4 edge USB transfer validation'


def disk():
    if not volume.exists():
        return dict(M6Present=False)
    result = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)]))
    assert result['BusProtocol'] == 'USB'
    assert (volume / 'marker.txt').read_text().strip() == marker
    result.update(M6Present=True, M6Marker=marker)
    written = volume / 'written.bin'
    result['M6WrittenSha256'] = hashlib.sha256(written.read_bytes()).hexdigest() if written.exists() else None
    return result


if command == 'probe':
    print(json.dumps(dict(brand=brand, hostname=hostname,
                         displays=json.loads(subprocess.check_output([root / 'hdmi-source-mode', 'list'], text=True)))))
elif command == 'hid':
    # Inherit SSH stdin; closing it restores the previous app and pointer.
    subprocess.run([root / 'input-target', '60'], check=True)
elif command == 'inspect':
    print(json.dumps(disk()))
elif command == 'write':
    info = disk()
    assert info['M6Present'] and info['WritableMedia']
    contents = bytes((i * 17 + 31) & 255 for i in range(1024 * 1024))
    with (volume / 'written.bin').open('xb') as stream:
        stream.write(contents)
        stream.flush()
        __import__('os').fsync(stream.fileno())
    assert (volume / 'written.bin').read_bytes() == contents
    print(json.dumps(disk()))
elif command == 'eject':
    info = disk()
    assert info['M6Present']
    subprocess.run(['diskutil', 'eject', info.get('ParentWholeDisk', info['DeviceIdentifier'])], check=True)
else:
    raise SystemExit('Expected probe, hid, inspect, write or eject')

