#!/usr/bin/env python3
"""Stage a final-release bundle, then deploy in one board/heavy lock window.

stage is offline. window/rollback default to dry-run; --execute takes both Mac
lockf locks for backup, install, regression and recovery. Success retains the
candidate. Critical failures trigger recovery; other failures are recorded.
Bundles staged with --require-all-checks recover on any regression/health failure.
SSH/serial failure is reported
without claiming recovery. Never builds kernels, pushes, or updates source pins.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
RECIPE = Path(__file__).resolve().parent
REMOTE = '/var/tmp/vim4-deploy-7.3-final'
REQUIRED_CHECKS = {'hdmi-modes', 'h264', 'h265', '4k60', 'audio', 'hid', 'media', 'gpu', 'manager'}
OPTIONAL_CHECKS = {'wifi'}
CRITICAL_CHECKS = {'hdmi-modes', 'h264', 'h265', 'hid'}


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def run(*args, **options):
    print('+', shlex.join(list(map(str, args))), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **options)


def git_revision(source, expected):
    assert re.fullmatch(r'[0-9a-f]{40}', expected), 'Full commit hashes are required'
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == expected, (source, actual, expected)
    assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()


def elf_arm64(path):
    header = path.read_bytes()[:20]
    assert header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 183, path


def checks(plan):
    identifiers = {item['id'] for item in plan}
    assert REQUIRED_CHECKS <= identifiers <= REQUIRED_CHECKS | OPTIONAL_CHECKS, 'Every regression category is required'
    assert len(plan) == len(identifiers), 'Duplicate regression category'
    for item in plan:
        assert item['argv'] and all(isinstance(arg, str) and arg for arg in item['argv'])
        assert 0 < item['timeout'] <= 1800
    return plan


def validate_bundle(bundle):
    deployment = json.loads((bundle / 'deployment.json').read_text())
    checks(deployment['checks'])
    for component, commit in deployment['commits'].items():
        assert re.fullmatch(r'[0-9a-f]{40}', commit), component
    for name, expected in deployment['sha256'].items():
        assert Path(name).name == name, 'Bundle entries must be flat files'
        assert sha(bundle / name) == expected, name
    report = json.loads((bundle / 'manifest.json').read_text())
    proof = json.loads((bundle / 'runtime-proof.json').read_text())
    release = '7.3.0-vim4kvm-uhd1+'
    assert report['source'] == deployment['commits']['kernel']
    assert report['release'] == proof['release'] == release
    assert b'Linux version ' + release.encode() + b' ' in (bundle / 'Image').read_bytes()
    assert (bundle / 'vim4.dtb').read_bytes()[:4] == b'\xd0\x0d\xfe\xed'
    assert proof['image_sha256'] == report['artifacts']['Image']
    for name, expected in report['artifacts'].items():
        assert sha(bundle / name) == expected
    files = {}
    with tarfile.open(bundle / 'modules.tar.gz') as archive:
        for member in archive:
            parts = Path(member.name).parts
            assert parts and parts[0] == release and '..' not in parts
            assert member.isdir() or member.isfile()
            if member.isfile():
                with archive.extractfile(member) as stream:
                    files[str(Path(*parts[1:]))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert files == report['modules'], 'Archive and complete module manifest differ'
    modules = {name: value for name, value in files.items() if name.endswith(('.ko', '.ko.xz', '.ko.zst'))}
    assert modules and len(modules) == report['module_count']
    assert modules == proof['module_sha256'], 'Registration proof does not match staged modules'
    elf_arm64(bundle / 'one-kvm')
    elf_arm64(bundle / 'vim4-manager')
    return deployment


def stage(args):
    git_revision(args.one_kvm_source, args.one_kvm_commit)
    git_revision(args.manager_source, args.manager_commit)
    assert re.fullmatch(r'[0-9a-f]{40}', args.kernel_commit)
    report = json.loads((args.kernel_payload / 'manifest.json').read_text())
    assert report['source'] == args.kernel_commit
    assert report['release'] == '7.3.0-vim4kvm-uhd1+'
    for name, expected in report['artifacts'].items():
        assert sha(args.kernel_payload / name) == expected, name
    elf_arm64(args.one_kvm_binary)
    elf_arm64(args.manager_binary)
    if args.ir_keytable:
        elf_arm64(args.ir_keytable)
    # Go embeds source identity. Reject binaries built before the manager commit.
    metadata = subprocess.check_output(['go', 'version', '-m', str(args.manager_binary)],
                                       env={k: v for k, v in os.environ.items() if k != 'GOROOT'}, text=True)
    assert 'vcs.revision=' + args.manager_commit in metadata
    assert 'vcs.modified=false' in metadata
    plan = checks(json.loads(args.regression.read_text()))
    args.bundle.mkdir()
    if args.ir_keytable:
        shutil.copy2(args.ir_keytable, args.bundle / 'ir-keytable')
    for name in ('Image', 'vim4.dtb', 'modules.tar.gz', 'manifest.json', 'runtime-proof.json'):
        shutil.copy2(args.kernel_payload / name, args.bundle / name)
    install = []

    def add(source, filename, target, mode=0o755):
        shutil.copy2(source, args.bundle / filename)
        install.append(dict(file=filename, target=target, mode=mode))

    for name in ('vim4-board-runtime', 'vim4-kvm-run'):
        add(ROOT / 'board' / name, name, '/usr/libexec/' + name)
    if not args.kernel_only:
        add(ROOT / 'board/60-vim4-panic.conf', '60-vim4-panic.conf',
            '/usr/lib/sysctl.d/60-vim4-panic.conf', 0o644)
    add(ROOT / 'board/vim4pd.py', 'vim4pd.py', '/usr/lib/vim4-kvm/python/vim4pd.py', 0o644)
    add(ROOT / 'board/vim4-kvm-pd.service', 'vim4-kvm-pd.service', '/usr/lib/systemd/system/vim4-kvm-pd.service', 0o644)
    # board/install.sh may have installed a higher-priority /etc unit.
    add(ROOT / 'board/vim4-kvm-pd.service', 'vim4-kvm-pd-etc.service', '/etc/systemd/system/vim4-kvm-pd.service', 0o644)
    if getattr(args, 'wave5_monitor', False):
        add(ROOT / 'board/vim4-wave5-monitor.py', 'vim4-wave5-monitor', '/usr/libexec/vim4-wave5-monitor')
        add(ROOT / 'board/vim4-wave5-monitor.service', 'vim4-wave5-monitor.service',
            '/etc/systemd/system/vim4-wave5-monitor.service', 0o644)
        add(ROOT / 'board/vim4-manager-wave5-monitor.conf', 'vim4-manager-wave5-monitor.conf',
            '/etc/systemd/system/vim4-manager.service.d/wave5-monitor.conf', 0o644)
    for source, target in (('one-kvm-edge-prepare', 'vim4-mainline-prepare'),
                           ('one-kvm-edge-usb-prepare', 'vim4-mainline-gadget-prepare')):
        add(RECIPE / source, target, '/usr/libexec/' + target)
    add(args.one_kvm_binary, 'one-kvm', '/opt/vim4-onekvm/one-kvm')
    add(args.manager_binary, 'vim4-manager', '/opt/vim4-manager/vim4-manager')
    add(args.manager_source / 'deploy/vim4-manager-helper', 'vim4-manager-helper', '/usr/libexec/vim4-manager-helper')
    for name in ('final-board.py', 'register-runtime.py'):
        shutil.copy2(RECIPE / name, args.bundle / name)
    deployment = dict(commits=dict(kernel=args.kernel_commit, onekvm=args.one_kvm_commit, manager=args.manager_commit),
                      install=install, checks=plan,
                      sha256={p.name: sha(p) for p in args.bundle.iterdir() if p.is_file()})
    assert re.fullmatch(r'[0-9a-f]{40}', args.baseline_build_id)
    deployment['baseline'] = dict(release=args.baseline_release, build_id=args.baseline_build_id)
    deployment['verify_pstore'] = args.verify_pstore
    deployment['framebuffer_console'] = args.framebuffer_console
    deployment['require_all_checks'] = args.require_all_checks
    if args.kernel_only:
        deployment['preserve'] = {item['target']: deployment['sha256'][item['file']] for item in install}
        deployment['install'] = []
    (args.bundle / 'deployment.json').write_text(json.dumps(deployment, indent=2) + '\n')
    validate_bundle(args.bundle)
    print('STAGED', args.bundle)


class Window:
    def __init__(self, args):
        self.args = args
        self.ssh = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=3', args.host]
        self.helper = shlex.join(['sudo', 'python3', REMOTE + '/final-board.py'])
        self.helper += ' --payload ' + shlex.quote(REMOTE) + ' --backup ' + shlex.quote(args.backup)

    def remote(self, command, **options):
        return run(*self.ssh, command, timeout=options.pop('timeout', 120), **options)

    def action(self, action):
        self.remote(self.helper + ' ' + shlex.quote(action), timeout=600)

    def reboot(self):
        old = subprocess.check_output(self.ssh + ['cat /proc/sys/kernel/random/boot_id'], text=True, timeout=10).strip()
        try:
            self.remote('sudo systemctl reboot', timeout=10)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            time.sleep(2)
            try:
                result = subprocess.run(self.ssh + ['cat /proc/sys/kernel/random/boot_id'], text=True,
                                        capture_output=True, timeout=10)
            except subprocess.TimeoutExpired:
                continue
            if result.returncode == 0 and result.stdout.strip() != old:
                self.remote('systemctl is-system-running --wait || test "$(systemctl is-system-running)" = degraded', timeout=90)
                return
        raise RuntimeError('SSH did not return; use serial/OOWOW recovery, no repeated reboot')

    def rollback(self):
        self.action('restore')
        self.reboot()
        self.action('verify-restore')

    def regression(self, item):
        with (self.args.logs / (item['id'] + '.log')).open('w') as log:
            child = subprocess.Popen(item['argv'], cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
            try:
                code = child.wait(timeout=item['timeout'])
                if code:
                    raise RuntimeError(f"Regression {item['id']} failed: {code}")
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
        print('REGRESSION_PASSED', item['id'], flush=True)

    def deploy(self):
        deployment = validate_bundle(self.args.bundle)
        archive = getattr(self.args, 'archive_remote_to', None)
        if archive:
            self.remote('test ! -e ' + shlex.quote(archive) + ' && mv ' + shlex.quote(REMOTE) + ' ' + shlex.quote(archive))
        self.remote('test ! -e ' + shlex.quote(REMOTE) + ' && mkdir ' + shlex.quote(REMOTE))
        run('scp', *sorted(self.args.bundle.glob('*')), self.args.host + ':' + REMOTE + '/')
        self.action('save')
        # Do not touch installed files until both backups exist and hashes match.
        local_backup = self.args.logs / 'baseline'
        local_backup.mkdir(mode=0o700)
        for name in ('files.tar', 'modules.tar', 'application.tar', 'state.json', 'warnings.txt', 'dmesg.txt'):
            with (local_backup / name).open('wb') as stream:
                self.remote('sudo cat ' + shlex.quote(self.args.backup + '/' + name), stdout=stream, timeout=600)
            expected = subprocess.check_output(self.ssh + ['sudo sha256sum ' + shlex.quote(self.args.backup + '/' + name)], text=True).split()[0]
            assert sha(local_backup / name) == expected, name
        changed = False
        try:
            changed = True
            self.action('install')
            self.reboot()
            self.action('verify')
            self.action('health')
            results = []
            for item in deployment['checks']:
                try:
                    self.regression(item)
                    results.append(dict(id=item['id'], passed=True))
                except (RuntimeError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
                    results.append(dict(id=item['id'], passed=False, error=str(error)))
                    if deployment.get('require_all_checks') or item['id'] in CRITICAL_CHECKS:
                        (self.args.logs / 'regression-results.json').write_text(json.dumps(results, indent=2) + '\n')
                        raise
                    print('NONCRITICAL_FAILURE', item['id'], str(error), flush=True)
                (self.args.logs / 'regression-results.json').write_text(json.dumps(results, indent=2) + '\n')
                # A peripheral test must not leave HID/capture broken silently.
                self.action('verify')
            self.action('health')
            if deployment.get('verify_pstore'):
                self.action('pstore-mark')
                self.reboot()
                self.action('verify')
                self.action('pstore-verify')
                # Check actual host input and the current manager after reboot.
                for item in deployment['checks']:
                    if item['id'] in ('hid', 'manager'):
                        self.regression(item)
                self.action('health')
            if deployment.get('require_all_checks'):
                self.remote('sudo python3 -c ' + shlex.quote(
                    'import json; p=json.load(open("' + REMOTE + '/health.json")); '
                    'assert all(item["passed"] for item in p.values()), p'))
            self.action('finalize')
            for name in ('health.json', 'warnings-after.txt'):
                with (self.args.logs / name).open('wb') as output:
                    self.remote('sudo cat ' + shlex.quote(REMOTE + '/' + name), stdout=output)
            print('SUCCESS: final deployment retained; no baseline reboot', flush=True)
        except BaseException:
            if changed:
                try:
                    with (self.args.logs / 'failure-board.log').open('wb') as output:
                        self.remote('sudo dmesg; sudo cat /sys/kernel/debug/fe398000.hdmi-receiver/status; '
                                    'sudo cat /sys/kernel/debug/ff000000.video-capture/status; '
                                    'sudo journalctl -b -u one-kvm -u vim4-manager -u vim4-kvm-pd --no-pager',
                                    stdout=output)
                except Exception as error:
                    print('Failed to capture board diagnostics:', error, flush=True)
                try:
                    with (self.args.logs / 'failure-source-mode.log').open('wb') as output:
                        run(ROOT / 'build/kernel-edge/mac-hdr-mode', stdout=output, stderr=subprocess.STDOUT, timeout=15)
                        run('/usr/sbin/system_profiler', 'SPDisplaysDataType', '-json',
                            stdout=output, stderr=subprocess.STDOUT, timeout=30)
                except Exception as error:
                    print('Failed to capture source diagnostics:', error, flush=True)
                try:
                    self.rollback()
                except Exception as error:
                    print('RECOVERY_NOT_VERIFIED:', error, 'Backup:', self.args.backup, flush=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    staging = commands.add_parser('stage')
    for name in ('kernel-payload', 'one-kvm-source', 'one-kvm-binary', 'manager-source', 'manager-binary', 'regression'):
        staging.add_argument('--' + name, type=Path, required=True)
    for name in ('kernel', 'one-kvm', 'manager'):
        staging.add_argument('--' + name + '-commit', required=True)
    staging.add_argument('--bundle', required=True, type=Path)
    staging.add_argument('--ir-keytable', type=Path, help='ARM64 IR health tool, kept inside the bundle')
    staging.add_argument('--baseline-release', default='7.3.0-rc7-vim4kvm-uhd1+')
    staging.add_argument('--baseline-build-id', default='52d5e46fb006230785110a1fa5ba0dd1383b732f')
    staging.add_argument('--kernel-only', action='store_true', help='Verify staged userspace files without replacing them')
    staging.add_argument('--wave5-monitor', action='store_true', help='Include the default log-only Wave5 quarantine monitor')
    staging.add_argument('--verify-pstore', action='store_true', help='Verify console retention across an extra normal reboot')
    staging.add_argument('--framebuffer-console', action='store_true', help='Register tty0 for a qualified simpledrm DTB')
    staging.add_argument('--require-all-checks', action='store_true', help='Roll back if any regression fails')
    for name in ('window', 'rollback'):
        command = commands.add_parser(name)
        command.add_argument('--bundle', required=True, type=Path)
        command.add_argument('--backup', required=True)
        command.add_argument('--logs', required=True, type=Path)
        command.add_argument('--host', default='vim4', choices=['vim4'])
        command.add_argument('--execute', action='store_true')
        command.add_argument('--dry-run', action='store_true')
        command.add_argument('--locked', action='store_true', help=argparse.SUPPRESS)
        command.add_argument('--archive-remote-to', help='Archive the previous attempt under both locks before staging')
    args = parser.parse_args()
    if args.command == 'stage':
        stage(args)
        return
    assert re.fullmatch(r'/var/backups/vim4-[A-Za-z0-9_-]+', args.backup)
    if args.archive_remote_to:
        assert re.fullmatch(r'/var/tmp/vim4-[A-Za-z0-9_.-]+', args.archive_remote_to)
        assert args.archive_remote_to != REMOTE
    if not args.execute or args.dry_run:
        if (args.bundle / 'deployment.json').exists():
            validate_bundle(args.bundle)
            print('OFFLINE_BUNDLE_VERIFIED')
        else:
            print('NOT_STAGED: artifact verification awaits the approved final commits and build')
        print(json.dumps(dict(command=args.command, bundle=str(args.bundle), backup=args.backup,
                              logs=str(args.logs), remote=REMOTE,
                              locks=['/tmp/vim4-board.lock', '/tmp/vim4-heavy.lock'],
                              steps=['backup board and Mac', 'install matched artifacts', 'reboot',
                                     'verify + required regression', 'retain unless startup/network/HID/capture fails']), indent=2))
        print('DRY_RUN: no SSH, no locks, no builds, no board writes')
        return
    if not args.locked:
        run('/usr/bin/lockf', '/tmp/vim4-board.lock', '/usr/bin/lockf', '/tmp/vim4-heavy.lock',
            sys.executable, Path(__file__).resolve(), *sys.argv[1:], '--locked')
        return
    assert not sys.flags.optimize, 'Run without -O: verification assertions are required'
    args.logs.mkdir(parents=True, exist_ok=False)
    window = Window(args)
    # Callers redirect stdout/stderr to retain the complete window transcript.
    serial = subprocess.Popen([sys.executable, str(ROOT / 'tools/uart-log.py'), '-q',
                               '-o', str(args.logs / 'uart.log')])
    try:
        if args.command == 'rollback':
            window.rollback()
        else:
            window.deploy()
    finally:
        serial.terminate()
        serial.wait(timeout=5)


if __name__ == '__main__':
    main()
