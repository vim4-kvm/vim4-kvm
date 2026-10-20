#!/usr/bin/env python3
"""macOS source-side EDID/DDC trial on the dedicated 7.3 VIM4 receiver kernel.

Pass at least two different valid EDID files already installed under the board's
/usr/lib/firmware/FIRMWARE_DIR. Requires exclusive board access and an unloaded
t7-hdmirx module. Each file is published on a fresh module load, compared with
both RAM readback and the Mac HDMI transport EDID, then unloaded.
This does not validate PHY lock, video capture or the advertised display modes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import time


def hdmi_ports():
    data = subprocess.check_output(['ioreg', '-a', '-r', '-c', 'IOPortTransportStateDisplayPort'])
    return [node for node in plistlib.loads(data)
            if node.get('ParentBuiltInPortTypeDescription') == 'HDMI']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--board', default='vim4')
    parser.add_argument('--firmware-dir', default='vim4-hdmirx-ddc-test')
    parser.add_argument('--log-dir', type=Path, required=True)
    parser.add_argument('edid', type=Path, nargs='+')
    args = parser.parse_args()
    if sys.platform != 'darwin' or len(args.edid) < 2:
        parser.error('Requires macOS and at least two different EDID files')
    payloads = [path.read_bytes() for path in args.edid]
    if len(set(payloads)) < 2:
        parser.error('Use distinct EDIDs to distinguish fresh DDC reads from cached metadata')
    for data in payloads:
        if len(data) not in (128, 256, 384, 512) or data[:8] != bytes.fromhex('00ffffffffffff00'):
            parser.error('Invalid EDID length or header')
        if data[126] != len(data) // 128 - 1 or any(sum(data[i:i+128]) % 256 for i in range(0, len(data), 128)):
            parser.error('Invalid EDID extension count or checksum')
    args.log_dir.mkdir(parents=True, exist_ok=False)

    def remote(command):
        return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                                        args.board, shlex.join(command)])

    release = remote(['uname', '-r']).decode().strip()
    if not release.startswith('7.3.0-rc7-vim4kvm-hdmirx'):
        raise RuntimeError(f'Requires the receiver trial kernel, found {release}')
    remote(['test', '!', '-e', '/sys/module/t7_hdmirx'])
    status_path = '/sys/kernel/debug/fe398000.hdmi-receiver/status'
    blob_path = '/sys/kernel/debug/fe398000.hdmi-receiver/edid'

    def observe(expected, label):
        deadline = time.monotonic() + 15
        while True:
            ports = hdmi_ports()
            (args.log_dir / f'{label}-ports.plist').write_bytes(plistlib.dumps(ports))
            active = [port for port in ports if port.get('Active')]
            if any(port.get('EDID') == expected and port.get('HPD_StateDescription') == 'High'
                   for port in active):
                return
            if time.monotonic() >= deadline:
                snapshot = [{key: port.get(key) for key in ('Active', 'HPD_StateDescription', 'ProductName')}
                            for port in ports]
                raise TimeoutError(f'HDMI source did not reach {label}: {snapshot}')
            time.sleep(.25)

    loaded = False
    try:
        (args.log_dir / 'before-ports.plist').write_bytes(plistlib.dumps(hdmi_ports()))
        for index, (path, data) in enumerate(zip(args.edid, payloads)):
            firmware = f'{args.firmware_dir}/{path.name}'
            # modprobe success alone does not prove the platform probe succeeded.
            remote(['sudo', '-n', 'modprobe', 't7-hdmirx', f'edid_firmware={firmware}'])
            loaded = True
            status = remote(['sudo', '-n', 'cat', status_path]).decode()
            (args.log_dir / f'{index}-status.txt').write_text(status)
            values = dict(line.split(': ', 1) for line in status.splitlines())
            if values['source_5v'] != '1' or values['hpd_request'] != '1':
                raise RuntimeError(f'Source cable power or HPD request missing: {values}')
            readback = remote(['sudo', '-n', 'cat', blob_path])
            if readback != data:
                raise RuntimeError('Receiver EDID readback differs from the fixture')
            observe(data, f'{index}-published')
            print(json.dumps({'cycle': index, 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest(),
                              'result': 'Mac HDMI transport read the exact EDID'}), flush=True)
            remote(['sudo', '-n', 'modprobe', '-r', 't7-hdmirx'])
            loaded = False
            (args.log_dir / f'{index}-unloaded-ports.plist').write_bytes(plistlib.dumps(hdmi_ports()))
        print('PASS: distinct EDIDs read by the HDMI source across module cycles', flush=True)
    finally:
        if loaded:
            subprocess.run(['ssh', '-o', 'BatchMode=yes', args.board,
                            'sudo -n modprobe -r t7-hdmirx'], check=False)
        (args.log_dir / 'dmesg.txt').write_bytes(remote(['sudo', '-n', 'dmesg']))


if __name__ == '__main__':
    main()
