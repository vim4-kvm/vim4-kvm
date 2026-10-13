#!/usr/bin/env python3
"""Explicit board recovery, verified image flashing, component deployment and smoke checks."""
import argparse
import base64
import contextlib
import fcntl
import getpass
import hashlib
import http.server
import ipaddress
import json
import lzma
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
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


# Base64 bytes per serial command; well below OOWOW's ~400-byte line limit.
UART_CHUNK = 200
# Stock Khadas account password; see docs/hardware.md (development only).
DEFAULT_PASSWORD = 'khadas'
COMPONENTS = ('vim4-kvm-board', 'vim4-vfmcap', 'vim4-amlvenc', 'vim4-nanokvm')


def package_metadata(directory):
    """Validate one ubuntu-build.py output set before copying it to the board."""
    directory = directory.resolve(strict=True)
    entries = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        entries[name.lstrip('*')] = digest
    version = directory.name
    debs = [directory / f'{name}_{version}_arm64.deb' for name in COMPONENTS]
    # Mixed versions would let dpkg pair a new server with old helpers.
    for path in debs + [directory / 'sources.json']:
        if path.name not in entries or not path.is_file():
            raise ValueError(f'{path.name} is missing from SHA256SUMS; expected all components at {version}')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != entries[path.name]:
                raise ValueError(f'{path.name} SHA256 does not match SHA256SUMS')
    sources = json.loads((directory / 'sources.json').read_text())
    dirty = sorted(name for name, source in sources['sources'].items() if source['dirty'])
    return version, debs, dirty


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
        self.password = self.password_read = None

    def note(self, message):
        print(message, flush=True)
        self.log.write(message + '\n')
        self.log.flush()

    def run(self, command, timeout=30, check=True, input_text=None, env=None):
        # Never inherit stdin: ssh would otherwise swallow a piped sudo password.
        stdin = None if input_text is not None else subprocess.DEVNULL
        result = subprocess.run(command, text=True, stdin=stdin, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, input=input_text, env=env)
        print(result.stdout, end='', flush=True)
        self.log.write(result.stdout)
        self.log.flush()
        if check and result.returncode:
            raise RuntimeError(f'Command failed ({result.returncode}); see log')
        return result

    def uart(self, command):
        return self.run([sys.executable, str(ROOT / 'tools/uart-run.py'),
                         '-d', self.args.device, '-t', '15', command], timeout=20).stdout

    def ssh(self, command, check=True, input_text=None, timeout=30):
        return self.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                         self.args.host, command], timeout=timeout, check=check, input_text=input_text)

    def sudo(self, command, timeout=30):
        # The password stays in memory and travels only on SSH stdin. -k makes
        # sudo always consume it; with cached credentials it would otherwise
        # reach the command's stdin.
        if not self.password_read:
            self.password_read = True
            if self.args.sudo_password_stdin:
                self.password = sys.stdin.readline().rstrip('\n') + '\n'
            elif self.ssh('sudo -n true', check=False).returncode:
                if not sys.stdin.isatty():
                    raise RuntimeError('sudo requires credentials; use --sudo-password-stdin with a secret provider')
                self.password = getpass.getpass('VIM4 sudo password: ') + '\n'
        prefix = "sudo -k -S -p '' " if self.password is not None else 'sudo -n '
        return self.ssh(prefix + command, input_text=self.password, timeout=timeout)

    def recover(self):
        # Authenticate before scheduling a reset. Never treat a dropped SSH link
        # as proof that OOWOW started; confirm its serial shell separately.
        self.ssh("grep -qi 'Khadas VIM4' /proc/device-tree/model && test -x /usr/local/bin/reboot2oowow")
        self.sudo("sh -c 'nohup sh -c \"sleep 2; sync; /usr/local/bin/reboot2oowow\" </dev/null >/tmp/vim4-recovery.log 2>&1 &'")
        self.run([sys.executable, str(ROOT / 'tools/uart-log.py'), '-d', self.args.device,
                  '-t', '60', '-o', str(self.args.log_dir / 'recovery-uart.log')], timeout=70)
        self.require_oowow(attempts=12)

    def require_oowow(self, attempts=1):
        # OOWOW boot time varies; a console that has not finished booting
        # just fails the probe, so poll instead of one fixed delay.
        for attempt in range(attempts):
            try:
                self.uart('test -d /www/x/api/disk && test -b /dev/mmcblk0')
                return
            except (RuntimeError, subprocess.SubprocessError):
                if attempt == attempts - 1:
                    raise RuntimeError('OOWOW shell not confirmed; inspect recovery-uart.log before retrying')
                time.sleep(10)

    def job(self, command, label, timeout):
        job = '/tmp/vim4-' + uuid.uuid4().hex
        self.note(f'{label}: remote log={job}.log status={job}.done')
        # OOWOW's console truncates lines near 400 bytes, leaving the shell in
        # an unterminated quote. Upload the command as short base64 chunks.
        encoded = base64.b64encode(command.encode()).decode()
        for offset in range(0, len(encoded), UART_CHUNK):
            self.uart(f"printf '%s' {encoded[offset:offset + UART_CHUNK]} >>{job}.b64")
        self.uart(f'base64 -d {job}.b64 >{job}.sh && test "$(wc -c <{job}.sh)" -eq {len(command.encode())}')
        self.uart(f'( sh {job}.sh >{job}.log 2>&1; echo $? >{job}.done ) </dev/null >/dev/null 2>&1 &')
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
        # Fresh images contain no developer key and new host keys.
        self.provision(replace_host_key=True)
        self.check()

    def enroll(self):
        # Copy first, then sudo install: the password must not share stdin
        # with file content.
        self.ssh("grep -qi 'Khadas VIM4' /proc/device-tree/model")
        remote = self.ssh('mktemp -d /tmp/vim4-enroll.XXXXXX').stdout.strip().splitlines()[-1]
        try:
            self.run(['scp', '-q', '-o', 'BatchMode=yes', str(ROOT / 'board/vim4-dev-nopasswd.sudoers'),
                      f'{self.args.host}:{remote}/'])
            self.sudo(f'sh -c "visudo -cf {remote}/vim4-dev-nopasswd.sudoers && '
                      f'install -m 0440 {remote}/vim4-dev-nopasswd.sudoers /etc/sudoers.d/vim4-dev-nopasswd"')
        finally:
            self.ssh(f'rm -rf {remote}', check=False)
        self.ssh('sudo -n true')
        self.note('Passwordless sudo enabled for unattended deploy/recover on this development board.')

    def ssh_config(self):
        output = subprocess.run(['ssh', '-G', self.args.host], text=True, capture_output=True, check=True).stdout
        config = {}
        for line in output.splitlines():
            key, _, value = line.partition(' ')
            config.setdefault(key, value)
        return config

    def provision(self, replace_host_key=False):
        """First access to a fresh image: install the developer key, then enroll."""
        config = self.ssh_config()
        address, user = config['hostname'], config['user']
        public_key = Path(os.path.expanduser(config['identityfile'])).with_suffix('.pub').read_text().strip()
        # Fresh images generate host keys on first boot and sshd starts late.
        deadline = time.monotonic() + 180
        while subprocess.run(['nc', '-z', '-w', '3', address, '22'], capture_output=True).returncode:
            if time.monotonic() > deadline:
                raise RuntimeError(f'SSH on {address} did not come up within 180 s')
            time.sleep(5)
        if replace_host_key:
            # Only after a flash we performed: the old key is known to be gone.
            self.run(['ssh-keygen', '-R', address], check=False)
        if self.ssh('true', check=False).returncode:
            self.note('Key login refused (expected on a fresh image); using the default account password.')
            # Stock credentials, documented in docs/hardware.md; the password
            # reaches ssh only through a private askpass helper's environment.
            with tempfile.TemporaryDirectory() as directory:
                askpass = Path(directory) / 'askpass'
                askpass.write_text('#!/bin/sh\nprintf "%s\\n" "$VIM4_PASSWORD"\n')
                askpass.chmod(0o700)
                env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE='force',
                           VIM4_PASSWORD=DEFAULT_PASSWORD)
                key = shlex.quote(public_key)
                self.run(['ssh', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'PubkeyAuthentication=no',
                          '-o', 'PreferredAuthentications=password', '-o', 'NumberOfPasswordPrompts=1',
                          '-o', 'ConnectTimeout=10', f'{user}@{address}',
                          f'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; '
                          f'grep -qxF {key} ~/.ssh/authorized_keys || echo {key} >> ~/.ssh/authorized_keys'],
                         env=env)
            self.ssh('true')
            self.note('Developer SSH key installed with the default account password.')
        if self.ssh('sudo -n true', check=False).returncode:
            if not self.args.sudo_password_stdin:
                self.password, self.password_read = DEFAULT_PASSWORD + '\n', True
            self.enroll()
        self.note('Provisioned: key login and passwordless sudo work.')

    def installed_versions(self):
        output = self.ssh("dpkg-query -W -f '${Package} ${Version}\\n' " + ' '.join(COMPONENTS), check=False).stdout
        return dict(line.split() for line in output.splitlines() if len(line.split()) == 2)

    def deploy(self, metadata):
        version, debs, dirty = metadata
        self.note(f'Packages={version} dirty_sources={",".join(dirty) or "none"}')
        self.ssh("grep -qi 'Khadas VIM4' /proc/device-tree/model")
        previous = self.installed_versions()
        # Recorded so an operator can redeploy the earlier build/packages set.
        self.note('Previous: ' + ' '.join(f'{name}={previous.get(name, "absent")}' for name in COMPONENTS))
        remote = self.ssh('mktemp -d /tmp/vim4-deploy.XXXXXX').stdout.strip().splitlines()[-1]
        try:
            # The installer checks every SHA256SUMS entry, so copy the whole set.
            files = sorted(path for path in debs[0].parent.iterdir() if path.is_file())
            self.run(['scp', '-q', '-o', 'BatchMode=yes', *map(str, files),
                      str(ROOT / 'tools/install-components.sh'), f'{self.args.host}:{remote}/'], timeout=300)
            # The board-side script owns verification, migration and restart;
            # keep a single installation implementation.
            self.sudo(f'bash {remote}/install-components.sh --exclusive {remote}', timeout=900)
        finally:
            self.ssh(f'rm -rf {remote}', check=False)
        installed = self.installed_versions()
        wrong = [name for name in COMPONENTS if installed.get(name) != version]
        if wrong:
            raise RuntimeError('Installed versions differ for ' + ', '.join(wrong))
        # Give the server time to bind 8080 before the smoke check.
        for _ in range(15):
            if not self.ssh('curl -fsS --max-time 2 -o /dev/null http://127.0.0.1:8080/', check=False).returncode:
                break
            time.sleep(1)
        self.check()

    def verify_hid(self):
        # Only meaningful when this Mac is the USB host of the gadget.
        if '"idProduct" = 260' not in subprocess.run(['ioreg', '-p', 'IOUSB', '-l', '-w0'], text=True,
                                                   capture_output=True).stdout:
            return 'SKIP', 'gadget is not attached to this Mac'
        original = host_pointer()
        write = lambda x, y: self.ssh("printf '" + ''.join(f'\\{b:03o}' for b in absolute_report(x, y))
                                      + "' > /dev/hidg1")
        try:
            for target in ((0.25, 0.25), (0.75, 0.6)):
                write(*target)
                time.sleep(0.3)
                actual = host_pointer()
                if max(abs(a - b) for a, b in zip(actual, target)) > 0.02:
                    return 'FAIL', f'pointer at {actual}, expected {target}'
        finally:
            write(*original)
        return 'PASS', 'absolute pointer reports moved the Mac cursor'

    def verify_audio(self):
        # The application may own the PCM while a client listens to audio.
        result = self.ssh('timeout 5 arecord -q -D hw:AMLAUGESOUND,0 -f S16_LE -r 48000 -c 2 -d 1 -t raw '
                          '| python3 -c "import sys,array; a=array.array(\'h\', sys.stdin.buffer.read()); '
                          'print(len(a)//2, max(map(abs, a), default=0))"', check=False)
        lines = result.stdout.split()
        if result.returncode or len(lines) < 2:
            if 'busy' in result.stdout.lower():
                return 'SKIP', 'PCM busy (application audio session active)'
            return 'FAIL', 'arecord failed: ' + result.stdout.strip()[-200:]
        frames, peak = int(lines[-2]), int(lines[-1])
        if frames < 40000:
            return 'FAIL', f'only {frames} frames in 1 s'
        return 'PASS', f'{frames} frames at 48 kHz, peak {peak} (0 means silent source)'

    def verify_video(self):
        module = os.environ.get('PLAYWRIGHT_MODULE')
        if not module and not shutil.which('node'):
            return 'SKIP', 'node is not installed'
        # Same address SSH uses, not whichever interface the board lists first.
        url = f'http://{self.ssh_config()["hostname"]}:8080'
        result = self.run(['node', str(ROOT / 'tools/video-smoke.mjs'), url, '10'], timeout=120, check=False)
        if result.returncode:
            if 'playwright' in result.stdout.lower() and 'cannot find' in result.stdout.lower():
                return 'SKIP', 'Playwright unavailable; set PLAYWRIGHT_MODULE'
            return 'FAIL', 'video-smoke.mjs failed; see log'
        stats = json.loads(result.stdout[result.stdout.index('{'):])
        return 'PASS', f'{stats["width"]}x{stats["height"]} {stats["decodedFps"]:.1f} fps, ' \
                       f'dropped {stats["framesDropped"]}, lost {stats["packetsLost"]}'

    def verify(self):
        self.check()
        results = {}
        for name, step in (('hid', self.verify_hid), ('audio', self.verify_audio), ('video', self.verify_video)):
            try:
                results[name] = step()
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                results[name] = ('FAIL', str(exc))
            self.note(f'{name}: {results[name][0]} - {results[name][1]}')
        (self.args.log_dir / 'verify.json').write_text(json.dumps(
            {name: {'status': status, 'detail': detail} for name, (status, detail) in results.items()}, indent=2))
        if any(status == 'FAIL' for status, _ in results.values()):
            raise RuntimeError('Functional verification failed')
        self.note('Verification finished; SKIP entries are not passes. Latency and keyboard input are not covered.')

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


POINTER_SCRIPT = (
    'ObjC.import("AppKit"); const p = $.NSEvent.mouseLocation; '
    'const f = $.NSScreen.screens.objectAtIndex(0).frame; '
    '[p.x / f.size.width, 1 - p.y / f.size.height].join(" ")')


def host_pointer():
    """Return the Mac cursor as fractions of the primary display, top-left origin."""
    output = subprocess.run(['osascript', '-l', 'JavaScript', '-e', POINTER_SCRIPT], text=True,
                            capture_output=True, check=True, timeout=10).stdout
    return tuple(float(value) for value in output.split())


def absolute_report(x, y):
    # hidg1 layout from kvm-gadget.sh: buttons, X and Y as LE 0..32767, wheel.
    to_axis = lambda value: max(0, min(32767, round(value * 32767)))
    return bytes([0]) + to_axis(x).to_bytes(2, 'little') + to_axis(y).to_bytes(2, 'little') + bytes([0])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['recover', 'flash', 'deploy', 'enroll', 'provision', 'check', 'verify'])
    parser.add_argument('--host', default='vim4')
    parser.add_argument('--device', default='/dev/cu.usbserial-100')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--packages', type=Path, help='ubuntu-build.py output, e.g. build/packages/VERSION')
    parser.add_argument('--serve-address', help='Mac LAN IPv4 reachable from OOWOW')
    parser.add_argument('--already-oowow', action='store_true')
    parser.add_argument('--sudo-password-stdin', action='store_true', help='read one password line; never store it in arguments or logs')
    parser.add_argument('--exclusive', action='store_true', help='assert other agents/serial terminals have released the board')
    parser.add_argument('--yes-erase-emmc', action='store_true')
    parser.add_argument('--kernel', default='5.15.137-vim4kvm')
    parser.add_argument('--dry-run', action='store_true', help='validate local inputs only; no SSH/UART/server')
    parser.add_argument('--log-dir', type=Path)
    parser.add_argument('--replace-host-key', action='store_true',
                        help='provision: forget the recorded host key (only after reinstalling the board)')
    args = parser.parse_args(argv)
    if args.action not in ('check', 'enroll', 'provision', 'verify') and not args.exclusive:
        parser.error('recover/flash/deploy requires --exclusive after coordinating board access')
    if args.action == 'flash':
        if not args.yes_erase_emmc or not args.image or not args.serve_address:
            parser.error('flash requires --yes-erase-emmc, --image and --serve-address')
        address = ipaddress.IPv4Address(args.serve_address)
        if address.is_unspecified or address.is_loopback or address.is_multicast:
            parser.error('--serve-address must be a reachable LAN IPv4 address')
        metadata = image_metadata(args.image)
        print(f'Image verified: {metadata[0].name}; raw bytes={metadata[3]}', flush=True)
    if args.action == 'deploy':
        if not args.packages:
            parser.error('deploy requires --packages')
        metadata = package_metadata(args.packages)
        print(f'Packages verified: {metadata[0]}', flush=True)
    if args.dry_run:
        sequences = {'flash': 'recover → OOWOW check → download/checksum → write → readback → reboot/log',
                     'deploy': 'copy → install-components.sh (checksum, APT simulate, migrate, restart nanokvm) → version check → check'}
        print(f'DRY RUN: {args.action}; no board access. Sequence: {sequences.get(args.action, args.action)}.')
        return
    args.log_dir = args.log_dir or ROOT / 'logs' / ('board-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    args.log_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    # Covers all board.py processes in this workspace, across SSH and UART phases.
    (ROOT / 'logs').mkdir(exist_ok=True)
    with (ROOT / 'logs/board.lock').open('w') as lock, (args.log_dir / 'operations.log').open('w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(f'Logs: {args.log_dir}', flush=True)
        if args.action in ('recover', 'flash'):
            # Fail before resetting a board when its serial adapter is missing,
            # busy, or cannot be configured at the expected baud rate.
            uart = __import__('uart-run')
            fd = uart.open_port(args.device, 921600)
            os.close(fd)
        board = Board(args, log)
        if args.action == 'flash':
            board.flash(metadata)
        elif args.action == 'deploy':
            board.deploy(metadata)
        elif args.action == 'enroll':
            board.enroll()
        elif args.action == 'verify':
            board.verify()
        elif args.action == 'provision':
            board.provision(args.replace_host_key)
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
