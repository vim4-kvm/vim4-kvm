#!/usr/bin/env python3
"""Run VBV controls/candidates locally on the board; caller must hold board/heavy locks.

Stops and restores an initially active One-KVM. Other KVM services must already
be inactive. Does not change HDMI, files in /usr, clocks, or application settings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def active(service):
    return subprocess.run(['systemctl', 'is-active', '--quiet', service]).returncode == 0


def service(action):
    subprocess.run(['sudo', '-n', 'systemctl', action, 'one-kvm'], check=True)


def run(args):
    for name in ['nanokvm', 'jetkvm', 'kvmd']:
        if active(name):
            raise RuntimeError(f'stop {name} before the exclusive experiment')
    if os.environ.get('LD_PRELOAD'):
        raise RuntimeError('refusing inherited LD_PRELOAD')
    args.directory.mkdir(parents=True, exist_ok=False)
    windows = []
    was_active = active('one-kvm')
    try:
        if was_active:
            service('stop')
        for codec in ['h264', 'h265']:
            for bitrate in [30000, 3000]:
                for label, vbv in [('stock', None), ('a1', 0), ('b500', 500), ('a2', 0), ('c100', 100), ('a3', 0)]:
                    name = f'{codec}-{bitrate}-{label}'
                    prefix = args.directory / name
                    env = dict(os.environ, GST_PLUGIN_PATH=args.plugin_path)
                    if vbv is not None:
                        env.update(LD_PRELOAD=str(args.probe), VBV_MS=str(vbv))
                    sensor = Path('/sys/class/thermal/thermal_zone0/temp')
                    temperature = [sensor.read_text().strip()]
                    print('START', name, flush=True)
                    with prefix.with_suffix('.log').open('w') as log:
                        subprocess.run([str(args.bench), 'run', str(args.fixture), codec,
                                        str(bitrate), '720', str(prefix)], env=env,
                                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
                    temperature.append(sensor.read_text().strip())
                    prefix.with_suffix('.temperature').write_text('\n'.join(temperature) + '\n')
                    with prefix.with_suffix('.' + codec).open('rb') as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    windows.append(dict(name=name, codec=codec, bitrate_kbps=bitrate, vbv_ms=vbv,
                                        result=digest, completed_at=time.time()))
                    (args.directory / 'windows.json').write_text(json.dumps(windows, indent=2))
        for codec in ['h264', 'h265']:
            for bitrate in [30000, 3000]:
                controls = [x['result'] for x in windows if x['codec'] == codec and
                            x['bitrate_kbps'] == bitrate and x['vbv_ms'] in (None, 0)]
                if len(set(controls)) != 1:
                    raise RuntimeError(f'{codec}/{bitrate}: original/observer controls differ')
    finally:
        if was_active:
            service('start')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', required=True, action='store_true')
    parser.add_argument('--bench', required=True, type=Path)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path, help='new evidence directory')
    parser.add_argument('--plugin-path', default='/usr/lib/vim4-kvm/gstreamer-1.0')
    args = parser.parse_args()
    for key in ['bench', 'probe', 'fixture']:
        setattr(args, key, getattr(args, key).resolve(strict=True))
    args.directory = args.directory.resolve()
    run(args)


if __name__ == '__main__':
    main()
