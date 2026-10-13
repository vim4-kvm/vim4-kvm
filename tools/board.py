#!/usr/bin/env python3
"""Explicit board recovery, verified image flashing and read-only smoke checks."""
import argparse
import contextlib
import fcntl
import getpass
import hashlib
import http.server
import ipaddress
import lzma
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def image_metadata(image):
    """Validate the exported artifact before changing any board state."""
    image = image.resolve(strict=True)
    if not image.is_file() or not image.name.endswith('.img.xz'):
        raise ValueError('Expected a regular .img.xz image')
    entries = {}
    for line in image.with_name('SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        entries[name.lstrip('*')] = digest
    with image.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if entries.get(image.name) != digest:
        raise ValueError('Image SHA256 does not match SHA256SUMS')
    raw_digest, size = hashlib.sha256(), 0
    with lzma.open(image, 'rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            raw_digest.update(chunk)
            size += len(chunk)
    sidecar = image.with_suffix('.sha256')
    if entries.get(sidecar.name) != hashlib.sha256(sidecar.read_bytes()).hexdigest():
        raise ValueError('Raw checksum sidecar is not in the verified manifest')
    if raw_digest.hexdigest() != sidecar.read_text().split()[0] or size == 0:
        raise ValueError('Uncompressed image SHA256 mismatch')
    return image, digest, raw_digest.hexdigest(), size


@contextlib.contextmanager
def serve_image(image, address):
    # Serve one unguessable URL, never a directory or other workspace files.
    route = '/' + uuid.uuid4().hex + '.img.xz'

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != route:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(image.stat().st_size))
            self.end_headers()
            with image.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    self.wfile.write(chunk)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer((address, 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://{address}:{server.server_port}{route}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


class Board:
    def __init__(self, args, log):
        self.args, self.log = args, log

    def note(self, message):
        print(message, flush=True)
        self.log.write(message + '\n')
        self.log.flush()

    def run(self, command, timeout=30, check=True, input_text=None):
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, input=input_text)
        print(result.stdout, end='', flush=True)
        self.log.write(result.stdout)
        self.log.flush()
        if check and result.returncode:
            raise RuntimeError(f'Command failed ({result.returncode}); see log')
        return result

    def uart(self, command):
        return self.run([sys.executable, str(ROOT / 'tools/uart-run.py'),
                         '-d', self.args.device, '-t', '15', command], timeout=20).stdout

    def ssh(self, command, check=True, input_text=None):
        return self.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                         self.args.host, command], check=check, input_text=input_text)

    def recover(self):
        # Authenticate before scheduling a reset. Never treat a dropped SSH link
        # as proof that OOWOW started; confirm its serial shell separately.
        self.ssh("grep -qi 'Khadas VIM4' /proc/device-tree/model && test -x /usr/local/bin/reboot2oowow")
        password = None
        if self.args.sudo_password_stdin:
            password = sys.stdin.readline().rstrip('\n') + '\n'
        elif self.ssh('sudo -n true', check=False).returncode:
            if not sys.stdin.isatty():
                raise RuntimeError('sudo requires credentials; use --sudo-password-stdin with a secret provider')
            password = getpass.getpass('VIM4 sudo password: ') + '\n'
        sudo = "sudo -S -p ''" if password is not None else 'sudo -n'
        self.ssh(sudo + " sh -c 'nohup sh -c \"sleep 2; sync; /usr/local/bin/reboot2oowow\" </dev/null >/tmp/vim4-recovery.log 2>&1 &'", input_text=password)
        self.run([sys.executable, str(ROOT / 'tools/uart-log.py'), '-d', self.args.device,
                  '-t', '60', '-o', str(self.args.log_dir / 'recovery-uart.log')], timeout=70)
        self.require_oowow()

    def require_oowow(self):
        self.uart('test -d /www/x/api/disk && test -b /dev/mmcblk0')

    def job(self, command, label, timeout):
        job = '/tmp/vim4-' + uuid.uuid4().hex
        self.note(f'{label}: remote log={job}.log status={job}.done')
        self.uart(f'( ( {command} ) >{job}.log 2>&1; echo $? >{job}.done ) </dev/null >/dev/null 2>&1 &')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            output = self.uart(f'if test -f {job}.done; then printf "STATUS="; cat {job}.done; cat {job}.log; else echo RUNNING; fi')
            statuses = [line for line in output.splitlines() if line.startswith('STATUS=')]
            if statuses:
                if statuses[0] != 'STATUS=0':
                    raise RuntimeError(f'{label} failed; remote log {job}.log')
                return
            time.sleep(5)
        raise RuntimeError(f'{label} timed out; may still be running. Inspect {job}.done and {job}.log; do not retry/reboot')

    def flash(self, metadata):
        image, compressed_sha, raw_sha, raw_size = metadata
        self.note(f'Image={image} SHA256={compressed_sha} raw_SHA256={raw_sha} raw_bytes={raw_size}')
        if not self.args.already_oowow:
            self.recover()
        self.require_oowow()
        remote = '/tmp/vim4-image-' + uuid.uuid4().hex + '.xz'
        # Capacity and board identity are checked before writing. Use the raw
        # image size, not the compressed archive length.
        self.uart("grep -qi 'Khadas VIM4' /proc/device-tree/model && "
                  f'test "$(cat /sys/class/block/mmcblk0/size)" -ge {(raw_size + 511) // 512} && '
                  "! grep -q '/dev/mmcblk0' /proc/mounts")
        with serve_image(image, self.args.serve_address) as url:
            self.job(f'curl -fSL --connect-timeout 15 --max-time 900 -o {remote} {shlex.quote(url)} && '
                     f'echo "{compressed_sha}  {remote}" | sha256sum -c - && xz -t {remote}',
                     'download and checksum', 1200)
        self.job(f'curl -fS --max-time 1800 -T {remote} http://127.0.0.1/api/disk/write/mmc.xz', 'write', 1900)
        self.job(f'sync && head -c {raw_size} /dev/mmcblk0 | sha256sum >{remote}.readback && '
                 f'test "$(cut -d " " -f1 {remote}.readback)" = {raw_sha}', 'readback verification', 1800)
        self.note('FLASH VERIFIED. Rebooting; UART output follows.')
        self.run([sys.executable, str(ROOT / 'tools/uart-log.py'), '-d', self.args.device,
                  '-t', '180', '-o', str(self.args.log_dir / 'firstboot-uart.log'),
                  '--send', 'sync; reboot'], timeout=190)
        # Fresh images intentionally do not contain the developer SSH key.
        self.note('Flash and boot capture complete. Run check after verifying SSH identity and installing your public key.')

    def check(self):
        # is-active with multiple units succeeds if ANY unit is active.
        self.ssh("set -eu; for service in tvserver vim4-kvm-hdmi vim4-kvm-gadget nanokvm; do "
                 "printf '%s: ' \"$service\"; systemctl is-active \"$service\"; done")
        self.ssh("set -eu; uname -r; test \"$(uname -r)\" = " + shlex.quote(self.args.kernel) + "; "
                 "test -e /dev/video_cap; test -e /dev/hidg0; test -e /dev/hidg1; test -e /dev/hidg2; "
                 "curl -fsS --max-time 10 http://127.0.0.1:8080/ >/dev/null; "
                 "cat /sys/class/udc/*/state; systemctl --failed --no-pager; "
                 "test -z \"$(systemctl --failed --no-legend --plain)\"")
        self.note('Smoke checks passed; this does not verify video, audio, HID input or latency end to end.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['recover', 'flash', 'check'])
    parser.add_argument('--host', default='vim4')
    parser.add_argument('--device', default='/dev/cu.usbserial-100')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--serve-address', help='Mac LAN IPv4 reachable from OOWOW')
    parser.add_argument('--already-oowow', action='store_true')
    parser.add_argument('--sudo-password-stdin', action='store_true', help='read one password line; never store it in arguments or logs')
    parser.add_argument('--exclusive', action='store_true', help='assert other agents/serial terminals have released the board')
    parser.add_argument('--yes-erase-emmc', action='store_true')
    parser.add_argument('--kernel', default='5.15.137-vim4kvm')
    parser.add_argument('--dry-run', action='store_true', help='validate local inputs only; no SSH/UART/server')
    parser.add_argument('--log-dir', type=Path)
    args = parser.parse_args(argv)
    if args.action != 'check' and not args.exclusive:
        parser.error('recover/flash requires --exclusive after coordinating board access')
    if args.action == 'flash':
        if not args.yes_erase_emmc or not args.image or not args.serve_address:
            parser.error('flash requires --yes-erase-emmc, --image and --serve-address')
        address = ipaddress.IPv4Address(args.serve_address)
        if address.is_unspecified or address.is_loopback or address.is_multicast:
            parser.error('--serve-address must be a reachable LAN IPv4 address')
        metadata = image_metadata(args.image)
        print(f'Image verified: {metadata[0].name}; raw bytes={metadata[3]}', flush=True)
    if args.dry_run:
        print(f'DRY RUN: {args.action}; no board access. Flash sequence: recover → OOWOW check → download/checksum → write → readback → reboot/log.')
        return
    args.log_dir = args.log_dir or ROOT / 'logs' / ('board-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    args.log_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    # Covers all board.py processes in this workspace, across SSH and UART phases.
    (ROOT / 'logs').mkdir(exist_ok=True)
    with (ROOT / 'logs/board.lock').open('w') as lock, (args.log_dir / 'operations.log').open('w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(f'Logs: {args.log_dir}', flush=True)
        if args.action != 'check':
            # Fail before resetting a board when its serial adapter is missing,
            # busy, or cannot be configured at the expected baud rate.
            uart = __import__('uart-run')
            fd = uart.open_port(args.device, 921600)
            os.close(fd)
        board = Board(args, log)
        if args.action == 'flash':
            board.flash(metadata)
        elif args.action == 'recover':
            board.recover()
        else:
            board.check()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
