#!/usr/bin/env python3
"""Board half of final-window.py. Only run under the coordinator's two locks."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import sqlite3
import struct
import subprocess
import tarfile
import time

BASE_RELEASE = '7.3.0-rc7-vim4kvm-uhd1+'
BASE_ID = '52d5e46fb006230785110a1fa5ba0dd1383b732f'
RELEASE = '7.3.0-vim4kvm-uhd1+'
IMAGE = Path('/boot/edge/Image')
DTB = Path('/boot/edge/vim4.dtb')
MODULES = Path('/lib/modules') / RELEASE
LUN = Path('/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file')
PSTORE_MASK = Path('/etc/systemd/system/systemd-pstore.service')


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def run(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def notes(path):
    data = Path(path).read_bytes()
    cursor, result = 0, []
    while cursor + 12 <= len(data):
        namesize, descsize, kind = struct.unpack_from('<III', data, cursor)
        cursor += 12
        name = data[cursor:cursor + namesize].rstrip(b'\0')
        cursor += (namesize + 3) // 4 * 4
        desc = data[cursor:cursor + descsize]
        cursor += (descsize + 3) // 4 * 4
        if name == b'GNU' and kind == 3:
            result.append(desc.hex())
    return result


def tree(root):
    return {str(p.relative_to(root)): {'link': os.readlink(p)} if p.is_symlink() else {'sha256': sha(p)}
            for p in sorted(root.rglob('*')) if p.is_symlink() or p.is_file()}


def firmware_hash():
    with Path('/dev/mmcblk0').open('rb', buffering=0) as disk:
        disk.seek(672256)
        data = disk.read(2576384)
    assert len(data) == 2576384
    return hashlib.sha256(data).hexdigest()


def wait_for_status(path, required, timeout=35):
    """Allow EDID/source restoration to settle, but bound persistent faults."""
    deadline = time.monotonic() + timeout
    recovering = False
    while True:
        text = path.read_text()
        if all(value in text for value in required):
            if recovering:
                print('STATUS_RECOVERED', path, flush=True)
            return text
        if time.monotonic() >= deadline:
            raise RuntimeError(f'HDMI/capture did not recover within {timeout}s: {path}\n{text}')
        if not recovering:
            print('WAITING_FOR_STATUS', path, text, flush=True)
            recovering = True
        time.sleep(.25)


def atomic_copy(source, target, mode=None):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.deploy-next')
    shutil.copy2(source, temporary)
    if mode is not None:
        temporary.chmod(mode)
    os.replace(temporary, target)


def bounded_command(args, timeout=10):
    """Do not wait again after killing a process that might be in D state."""
    # A surviving D-state child must not retain the recovery SSH channel either.
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as error:
        print('RECOVERY_COMMAND_UNAVAILABLE', args, str(error), flush=True)
        return False
    try:
        result = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        except OSError as error:
            print('RECOVERY_COMMAND_KILL_FAILED', args, str(error), flush=True)
        print('RECOVERY_COMMAND_TIMEOUT', args, flush=True)
        return False
    if result:
        print('RECOVERY_COMMAND_FAILED', result, args, flush=True)
    return result == 0


def sync_restored_files(state):
    # syncfs on local restored filesystems avoids an unrelated stuck CIFS mount.
    # A timeout is reported as incomplete durability, never as successful restore.
    paths = {str(MODULES.parent), '/boot'}
    paths.update(str(Path(name).parent) for name in state['files'])
    failed = [path for path in sorted(paths)
              if not bounded_command(['sync', '-f', path], timeout=30)]
    if failed:
        raise RuntimeError('Recovery files written, but sync failed: ' + ', '.join(failed))


class Board:
    def __init__(self, payload, backup):
        self.payload, self.backup = payload, backup
        self.deployment = json.loads((payload / 'deployment.json').read_text())
        self.report = json.loads((payload / 'manifest.json').read_text())
        self.baseline = self.deployment.get('baseline', dict(release=BASE_RELEASE, build_id=BASE_ID))

    def preserve(self):
        for path, expected in self.deployment.get('preserve', {}).items():
            assert sha(path) == expected, path

    def preflight(self):
        assert os.uname().release == self.baseline['release'], 'Unexpected running baseline'
        assert notes('/sys/kernel/notes') == [self.baseline['build_id']]
        self.preserve()
        assert run('systemctl', 'is-active', 'vim4-manager') == 'active'
        assert run('systemctl', 'is-active', 'one-kvm') == 'active'
        assert not LUN.read_text().strip(), 'Safely eject active media first'
        if self.baseline['release'] != RELEASE:
            assert not MODULES.exists(), 'Do not overwrite an unrelated release directory'
        if self.deployment.get('verify_pstore'):
            assert not PSTORE_MASK.exists() and not PSTORE_MASK.is_symlink()
        assert not self.backup.exists()
        assert Path('/lib').is_symlink() and not IMAGE.is_symlink() and not DTB.is_symlink()
        for name, expected in self.deployment['sha256'].items():
            assert sha(self.payload / name) == expected, name
        # Reject an administrator's PD override instead of silently bypassing
        # either its policy or our boot-only service guard.
        for directory in ('/etc/systemd/system/vim4-kvm-pd.service.d',
                          '/run/systemd/system/vim4-kvm-pd.service.d'):
            assert not list(Path(directory).glob('*.conf')), directory
        assert self.report['release'] == RELEASE
        assert self.report['source'] == self.deployment['commits']['kernel']
        assert shutil.disk_usage('/').free > 2 * (self.payload / 'modules.tar.gz').stat().st_size + 400_000_000
        # The old Image is backed up to rootfs; /boot cannot hold two copies.
        assert shutil.disk_usage('/boot').free + IMAGE.stat().st_size > (self.payload / 'Image').stat().st_size + 4_000_000
        print('PREFLIGHT_OK', flush=True)

    def save(self):
        self.preflight()
        self.backup.mkdir(mode=0o700)
        paths = {str(IMAGE), str(DTB), '/boot/extlinux/extlinux.conf',
                 '/etc/vim4-kvm/kernels.json', '/etc/vim4-kvm/runtime-build.json',
                 *[item['target'] for item in self.deployment['install']]}
        if self.deployment.get('verify_pstore'):
            paths.add(str(PSTORE_MASK))
        existing, missing = [], []
        for name in sorted(paths):
            (existing if Path(name).exists() else missing).append(name)
        subprocess.run(['tar', '-cpf', str(self.backup / 'files.tar'), '-C', '/',
                        *[p.lstrip('/') for p in existing]], check=True)
        subprocess.run(['tar', '-cpf', str(self.backup / 'modules.tar'), '-C', '/lib/modules', self.baseline['release']], check=True)
        # SQLite's backup API gives a consistent snapshot while the application
        # is running. Media images are deliberately excluded from this archive.
        app = self.backup / 'application'
        app.mkdir()
        with sqlite3.connect('file:/var/lib/one-kvm/one-kvm.db?mode=ro', uri=True) as source:
            with sqlite3.connect(app / 'one-kvm.db') as destination:
                source.backup(destination)
        metadata = Path('/var/lib/one-kvm/one-kvm.db').stat()
        os.chown(app / 'one-kvm.db', metadata.st_uid, metadata.st_gid)
        (app / 'one-kvm.db').chmod(metadata.st_mode & 0o777)
        directories = [name for name in ('mcp', 'uu-remote') if (Path('/var/lib/one-kvm') / name).exists()]
        subprocess.run(['tar', '-cpf', str(self.backup / 'application.tar'), '-C', str(app), 'one-kvm.db',
                        '-C', '/var/lib/one-kvm', *directories], check=True)
        state = dict(files={p: sha(p) for p in existing}, missing=missing, firmware_sha256=firmware_hash(),
                     modules=tree(Path('/lib/modules') / self.baseline['release']),
                     build_ids=notes('/sys/kernel/notes'), cmdline=Path('/proc/cmdline').read_text(),
                     links={p: os.readlink(p) for p in ('/lib', '/boot/Image', '/boot/dtb', '/boot/initrd.img')},
                     protected={str(p): sha(p) for pattern in ('vmlinuz-5.15*', 'initrd.img-5.15*')
                                for p in Path('/boot').glob(pattern) if p.is_file()})
        (self.backup / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
        (self.backup / 'warnings.txt').write_text(run('dmesg', '-k', '-l', 'err,warn'))
        (self.backup / 'dmesg.txt').write_text(run('dmesg'))
        (self.backup / 'COMPLETE').touch()
        self.prepare_rollback()
        os.sync()
        print('BACKUP_COMPLETE', self.backup, flush=True)

    def prepare_rollback(self):
        # Keep recovery independent of the staging directory and host process.
        recovery = self.backup / 'recovery'
        recovery.mkdir()
        for name in ('final-board.py', 'deployment.json', 'manifest.json'):
            shutil.copy2(self.payload / name, recovery / name)
        command = ' '.join(map(shlex.quote, ['python3', str(recovery / 'final-board.py'),
                            '--payload', str(recovery), '--backup', str(self.backup)]))
        script = self.backup / 'rollback.sh'
        script.write_text('#!/bin/sh\nset -eu\ncase "${1:-restore}" in\n'
                          f' restore) {command} restore ;;\n'
                          f' verify) {command} verify-restore ;;\n'
                          f' reboot) {command} restore; timeout -k 1 30 systemctl reboot --no-block </dev/null >/dev/null 2>&1 ;;\n'
                          ' *) echo "Usage: $0 [restore|reboot|verify]" >&2; exit 2 ;;\nesac\n')
        script.chmod(0o700)
        print('INDEPENDENT_ROLLBACK', script, flush=True)

    def install(self):
        assert (self.backup / 'COMPLETE').exists()
        staging = self.payload / 'staging'
        staging.mkdir()
        with tarfile.open(self.payload / 'modules.tar.gz') as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts
                assert parts and parts[0] == RELEASE and '..' not in parts
                assert member.isfile() or member.isdir(), 'Only module files and directories are allowed'
        subprocess.run(['tar', '--keep-directory-symlink', '-xzf', str(self.payload / 'modules.tar.gz'),
                        '-C', str(staging)], check=True)
        assert tree(staging / RELEASE) == {k: {'sha256': v} for k, v in self.report['modules'].items()}
        for name in ('one-kvm', 'vim4-manager'):
            bounded_command(['systemctl', 'stop', name])
        if self.baseline['release'] == RELEASE:
            MODULES.rename(self.backup / 'original-modules')
        (staging / RELEASE).rename(MODULES)
        if self.deployment.get('verify_pstore'):
            PSTORE_MASK.symlink_to('/dev/null')
        for item in self.deployment['install']:
            atomic_copy(self.payload / item['file'], item['target'], item['mode'])
        # PD is intentionally not started or restarted during runtime install.
        IMAGE.unlink()
        shutil.copy2(self.payload / 'Image', IMAGE)
        shutil.copy2(self.payload / 'vim4.dtb', DTB)
        os.sync()
        bounded_command(['systemctl', 'daemon-reload'])
        registration = ['python3', str(self.payload / 'register-runtime.py'), 'register',
                        str(self.payload / 'runtime-proof.json')]
        if self.deployment.get('framebuffer_console'):
            registration.append('--framebuffer-console')
        subprocess.run(registration, check=True)
        import sys
        sys.path.insert(0, '/usr/lib/vim4-kvm/python')
        import vim4boot
        vim4boot.select('mainline')
        os.sync()
        print('INSTALLED_REBOOT_REQUIRED', flush=True)

    def verify(self):
        self.preserve()
        assert os.uname().release == RELEASE
        assert notes('/sys/kernel/notes') == [self.report['kernel_build_id']]
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        assert hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest() == self.report['config_sha256']
        assert sha(IMAGE) == self.report['artifacts']['Image']
        assert sha(DTB) == self.report['artifacts']['vim4.dtb']
        assert tree(MODULES) == {k: {'sha256': v} for k, v in self.report['modules'].items()}
        for item in self.deployment['install']:
            assert sha(item['target']) == self.deployment['sha256'][item['file']]
        for service in ('one-kvm', 'vim4-manager', 'vim4-kvm-hdmi', 'vim4-kvm-gadget'):
            assert run('systemctl', 'is-active', service) == 'active', service
        for service, binary in (('one-kvm', 'one-kvm'), ('vim4-manager', 'vim4-manager')):
            pid = run('systemctl', 'show', '-p', 'MainPID', '--value', service)
            assert sha('/proc/' + pid + '/exe') == self.deployment['sha256'][binary]
        assert any(p.read_text().strip() == 'configured' for p in Path('/sys/class/udc').glob('*/state'))
        for path, required in (
            ('/sys/kernel/debug/fe398000.hdmi-receiver/status', ['source_5v: 1', 'link_ready: 1']),
            ('/sys/kernel/debug/ff000000.video-capture/status', ['faulted: 0', 'stream_error: 0']),
        ):
            wait_for_status(Path(path), required)
        print('CRITICAL_HEALTH_VERIFIED', self.report['kernel_build_id'], flush=True)

    def health(self):
        results = {}

        def check(name, operation):
            try:
                value = operation()
                assert value, 'Unexpected empty or false result'
                results[name] = dict(passed=True, evidence=value)
            except Exception as error:
                results[name] = dict(passed=False, error=str(error))

        def loaded_modules():
            for name, identifier in self.report['loaded_module_build_ids'].items():
                assert notes('/sys/module/' + name + '/notes/.note.gnu.build-id') == [identifier], name
            return self.report['loaded_module_build_ids']

        def fan():
            root = Path('/sys/bus/platform/devices/khadas-mcu-fan-ctrl')
            values = {name: int((root / name).read_text()) for name in ('sensor_fault', 'speed_percent', 'temperature_millic')}
            assert values['sensor_fault'] == 0 and 0 <= values['speed_percent'] <= 100
            assert 0 < values['temperature_millic'] < 85000
            return values

        def pd():
            journal = run('journalctl', '-b', '-u', 'vim4-kvm-pd', '--no-pager', '-o', 'cat')
            assert 'PD bootstrap skipped:' in journal or 'PD bootstrap repair:' in journal, journal
            assert run('systemctl', 'is-active', 'vim4-kvm-pd') == 'active'
            return journal

        def ir():
            assert '[nec]' in Path('/sys/class/rc/rc0/protocols').read_text()
            keytable = shutil.which('ir-keytable') or '/var/tmp/vim4-dtnodes-ir-keytable'
            table = subprocess.check_output([keytable], text=True, stderr=subprocess.STDOUT)
            assert 'rc-khadas' in table
            return table

        def rng():
            current = Path('/sys/class/misc/hw_random/rng_current').read_text().strip()
            assert current == 'fe440788.rng', current
            assert len(Path('/dev/hwrng').open('rb', buffering=0).read(32)) == 32
            return current + ': 32 bytes read'

        def manager():
            assert run('systemctl', 'is-active', 'vim4-manager') == 'active'
            pid = run('systemctl', 'show', '-p', 'MainPID', '--value', 'vim4-manager')
            digest = sha('/proc/' + pid + '/exe')
            assert digest == self.deployment['sha256']['vim4-manager']
            assert run('curl', '-fsS', 'http://127.0.0.1:80/login.html')
            return dict(pid=pid, sha256=digest)

        check('loaded_module_ids', loaded_modules)
        check('manager', manager)
        check('failed_units', lambda: not run('systemctl', '--failed', '--no-legend'))
        check('taint', lambda: Path('/proc/sys/kernel/tainted').read_text().strip() == '0')
        check('hwrng', rng)
        check('ir', ir)
        check('fan', fan)
        check('gpu_governor', lambda: Path('/sys/class/devfreq/fe400000.gpu/governor').read_text().strip() == 'simple_ondemand')
        check('pd', pd)
        normalize = lambda text: {re.sub(r'^\[[^]]+\]\s*', '', line) for line in text.splitlines()}
        warnings = run('dmesg', '-k', '-l', 'err,warn')
        (self.payload / 'warnings-after.txt').write_text(warnings)
        unexplained = sorted(normalize(warnings) - normalize((self.backup / 'warnings.txt').read_text()))
        print('NEW_WARNINGS', json.dumps(unexplained), flush=True)
        results['new_warnings'] = dict(passed=not unexplained, evidence=unexplained)
        (self.payload / 'health.json').write_text(json.dumps(results, indent=2) + '\n')
        print('HEALTH_REPORT', json.dumps(results), flush=True)

    def restore(self):
        assert (self.backup / 'COMPLETE').exists()
        state = json.loads((self.backup / 'state.json').read_text())
        stopped = [bounded_command(['systemctl', 'stop', service])
                   for service in ('one-kvm', 'vim4-manager')]
        pending = self.backup / 'application-restore-pending'
        # Persist this before file writes: interruption must not look complete.
        pending.write_text('Application restore requires stopped services.\n')
        # Files may be executable/in use. Unlink only our replaced payloads;
        # extraction retains /lib and preserves original file metadata.
        for name in state['files']:
            Path(name).unlink(missing_ok=True)
        subprocess.run(['tar', '--keep-directory-symlink', '-xpf', str(self.backup / 'files.tar'), '-C', '/'], check=True)
        for name in state['missing']:
            Path(name).unlink(missing_ok=True)
        self.restore_modules()
        # Secure the boot path before attempting any application/database work.
        try:
            sync_restored_files(state)
            if all(stopped):
                self.restore_application()
            else:
                print('APPLICATION_RESTORE_DEFERRED', pending, flush=True)
        finally:
            bounded_command(['systemctl', 'daemon-reload'])
        print('RESTORED_REBOOT_REQUIRED', flush=True)

    def restore_application(self):
        for suffix in ('-wal', '-shm'):
            Path('/var/lib/one-kvm/one-kvm.db' + suffix).unlink(missing_ok=True)
        subprocess.run(['tar', '-xpf', str(self.backup / 'application.tar'), '-C', '/var/lib/one-kvm'], check=True)
        shutil.chown('/var/lib/one-kvm/one-kvm.db', user='khadas', group='khadas')
        if not bounded_command(['sync', '-f', '/var/lib/one-kvm'], timeout=30):
            raise RuntimeError('Application restored but sync failed')
        (self.backup / 'application-restore-pending').unlink(missing_ok=True)

    def restore_modules(self):
        original = self.backup / 'original-modules'
        # Before the rename, a partial install still has the baseline in place.
        if self.baseline['release'] == RELEASE and not original.exists():
            state = json.loads((self.backup / 'state.json').read_text())
            assert tree(MODULES) == state['modules']
            return
        if MODULES.exists():
            MODULES.rename(self.backup / 'candidate-modules')
        if original.exists():
            original.rename(MODULES)

    def verify_restore(self):
        assert not (self.backup / 'application-restore-pending').exists(), 'Application restore pending'
        state = json.loads((self.backup / 'state.json').read_text())
        assert os.uname().release == self.baseline['release'] and notes('/sys/kernel/notes') == [self.baseline['build_id']]
        assert tree(Path('/lib/modules') / self.baseline['release']) == state['modules']
        self.preserve()
        for name, expected in {**state['files'], **state['protected']}.items():
            assert sha(name) == expected, name
        for name, target in state['links'].items():
            assert os.readlink(name) == target
        assert Path('/proc/cmdline').read_text() == state['cmdline']
        assert run('systemctl', 'is-active', 'vim4-manager') == 'active'
        assert run('systemctl', 'is-active', 'one-kvm') == 'active'
        print('BASELINE_RESTORED', self.baseline['build_id'], flush=True)

    def pstore_mark(self):
        assert self.deployment.get('verify_pstore')
        assert Path('/sys/bus/platform/drivers/ramoops/7400000.ramoops').exists()
        assert ' /sys/fs/pstore pstore ' in Path('/proc/mounts').read_text()
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        marker = 'VIM4_PSTORE_DEPLOY_' + Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        (self.payload / 'pstore-marker').write_text(marker)
        # Ubuntu's console threshold is 4; info messages only reach dmesg.
        Path('/dev/kmsg').write_text('<3>' + marker + '\n')
        os.sync()
        print('PSTORE_MARKED', marker, flush=True)

    def pstore_verify(self):
        marker = (self.payload / 'pstore-marker').read_text()
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() not in marker
        records = {p.name: p.read_bytes() for p in Path('/sys/fs/pstore').glob('console-ramoops-*')}
        assert any(marker.encode() in data for data in records.values()), 'Previous console marker missing'
        saved = self.payload / 'pstore-readback'
        saved.mkdir()
        for name, data in records.items():
            (saved / name).write_bytes(data)
        print('PSTORE_READBACK', marker, {name: len(data) for name, data in records.items()}, flush=True)
        assert PSTORE_MASK.is_symlink() and os.readlink(PSTORE_MASK) == '/dev/null'
        PSTORE_MASK.unlink()
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'start', 'systemd-pstore'], check=True)

    def finalize(self):
        self.verify()
        state = json.loads((self.backup / 'state.json').read_text())
        assert firmware_hash() == state['firmware_sha256'], 'U-Boot changed during deployment'
        print('UBOOT_UNCHANGED', state['firmware_sha256'], flush=True)
        for name, expected in state['protected'].items():
            assert sha(name) == expected, name
        path = Path('/etc/vim4-kvm/runtime-build.json')
        runtime = json.loads(path.read_text())
        runtime.update(kernel_source=self.report['source'], kernel_build_id=self.report['kernel_build_id'],
                       running=RELEASE,
                       module_archive_sha256=self.report['artifacts']['modules.tar.gz'],
                       config_sha256=self.report['config_sha256'], module_count=self.report['module_count'],
                       deployed_components=self.deployment['commits'], deployment_backup=str(self.backup))
        hashes = runtime.setdefault('sha256', {})
        hashes.update({str(IMAGE): sha(IMAGE), str(DTB): sha(DTB)})
        hashes.update({item['target']: sha(item['target']) for item in self.deployment['install']})
        hashes.update(self.deployment.get('preserve', {}))
        path.write_text(json.dumps(runtime, indent=2) + '\n')
        os.sync()
        print('DEPLOYMENT_RETAINED', json.dumps(self.deployment['commits']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'save', 'install', 'verify', 'health', 'restore', 'verify-restore', 'finalize', 'pstore-mark', 'pstore-verify'))
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    board = Board(args.payload, args.backup)
    getattr(board, args.action.replace('-', '_'))()


if __name__ == '__main__':
    main()
