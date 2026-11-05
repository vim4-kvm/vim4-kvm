#!/usr/bin/env python3
"""Read-only early boot snapshots, started only by an opt-in RAM init.

Output must be a private tmpfs supplied by that init. Each snapshot runs in a
separate process so a slow sysfs getter cannot delay PID 1 or later snapshots.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def snapshot(root):
    def emit(path, **values):
        print(json.dumps(dict(path=path, monotonic_ns=time.monotonic_ns(), **values)), flush=True)

    def read(name):
        path = root / name.lstrip('/')
        try:
            with path.open('rb') as source:
                data = source.read(65537)
            if len(data) > 65536:
                raise ValueError('snapshot file exceeds 64 KiB')
            emit(name, value=data.decode(errors='replace'), sha256=hashlib.sha256(data).hexdigest())
        except (OSError, ValueError) as error:
            emit(name, error=str(error))

    for name in ('/proc/sys/kernel/random/boot_id', '/proc/cmdline', '/proc/uptime',
                 '/proc/modules', '/proc/sys/kernel/osrelease'):
        read(name)
    module_root = root / 'sys/module'
    emit('/sys/module/aml_vdec_drv', exists=(module_root/'aml_vdec_drv').exists())
    for path in sorted(module_root.glob('*/parameters/*')):
        read('/' + str(path.relative_to(root)))
    for prefix in ('etc', 'run', 'usr/local/lib', 'usr/lib', 'lib'):
        for directory in ('modprobe.d', 'modules-load.d'):
            location = root / prefix / directory
            emit('/'+prefix+'/'+directory, exists=location.exists())
            if location.is_dir():
                for path in sorted(location.iterdir()):
                    name = '/' + str(path.relative_to(root))
                    if path.is_symlink():
                        emit(name, symlink=os.readlink(path))
                    if path.is_file():
                        read(name)
    read('/etc/modules')
    if root == Path('/'):
        for command in (['/usr/sbin/lsmod'], ['/usr/sbin/modprobe', '--showconfig']):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=.5)
                emit('command', argv=command, returncode=result.returncode,
                     stdout=result.stdout, stderr=result.stderr)
            except (OSError, subprocess.SubprocessError) as error:
                emit('command', argv=command, error=str(error))


def capture(output, label, root=Path('/')):
    path = output / (label + '.jsonl')
    started = time.monotonic_ns()
    with path.open('x') as log:
        os.chmod(path, 0o600)
        try:
            result = subprocess.run([sys.executable, '-u', __file__, '--snapshot', '--root', str(root)],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=1)
            status = 'complete' if result.returncode == 0 else 'error'
        except subprocess.TimeoutExpired:
            status = 'timeout'
    summary = dict(label=label, status=status, started_monotonic_ns=started,
                   ended_monotonic_ns=time.monotonic_ns())
    (output/(label+'.status.json')).write_text(json.dumps(summary)+'\n')
    # Only these small fields go to UART. Full parameter/config text stays private.
    visible = []
    for line in path.read_text(errors='replace').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row['path'] in ('/proc/sys/kernel/random/boot_id', '/sys/module/aml_vdec_drv') or row['path'].startswith('/sys/module/aml_vdec_drv/parameters/'):
            visible.append(row)
    print('COLDBOOT_SNAPSHOT '+json.dumps(dict(summary, decoder=visible)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    if args.snapshot:
        snapshot(args.root)
        return
    if args.output is None:
        parser.error('--output is required')
    capture(args.output, 'initial', args.root)
    for target in (3, 5, 8, 15, 45, 60):
        uptime = float((args.root/'proc/uptime').read_text().split()[0])
        if uptime > target + .5:
            (args.output/f'{target}.status.json').write_text(json.dumps(
                dict(label=str(target), status='skipped', uptime=uptime))+'\n')
            continue
        time.sleep(max(0, target-uptime))
        capture(args.output, str(target), args.root)


if __name__ == '__main__':
    main()
