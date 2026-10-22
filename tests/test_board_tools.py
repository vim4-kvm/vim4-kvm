"""Offline safety boundaries; no board, SSH, sudo or device writes."""
import base64
import hashlib
import importlib.util
import io
import json
import lzma
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import unittest.mock
from unittest.mock import patch
import urllib.error
import urllib.request


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


board = load('board')
uart = load('uart-run')


class BoardToolsTests(unittest.TestCase):
    def test_mainline_health_uses_capture_devices_without_vendor_service_or_alias(self):
        instance = board.Board(SimpleNamespace(kernel='7.3.0-vim4kvm-uhd1+'), io.StringIO())
        environment = '''
        uname() { echo '7.3.0-vim4kvm-uhd1+'; }
        systemctl() {
            case "$*" in *tvserver*) return 3 ;; --failed*) return 0 ;; *) echo active ;; esac
        }
        test() {
            if [ "$1" = -e ]; then [ "$2" != /dev/video_cap ]; else command test "$@"; fi
        }
        python3() { return "$CAPTURE_STATUS"; }
        curl() { return 0; }
        cat() { echo configured; }
        '''
        def ssh(command):
            result = subprocess.run(['sh', '-c', environment + command], capture_output=True,
                                    text=True, env={**os.environ, 'CAPTURE_STATUS': capture_status})
            if result.returncode:
                raise RuntimeError('health failed')
            return result
        with patch.object(instance, 'ssh', side_effect=ssh):
            capture_status = '0'
            instance.check()
            capture_status = '1'
            with self.assertRaisesRegex(RuntimeError, 'health failed'):
                instance.check()

    def test_one_inactive_service_rejects_health_check(self):
        instance = board.Board(SimpleNamespace(kernel='5.15.137-vim4kvm'), io.StringIO())
        # Model systemctl's ANY-active exit status, including an inactive unit
        # which would not appear in `systemctl --failed`.
        fake_systemctl = '''systemctl() {
            shift
            result=3
            for unit in "$@"; do
                if [ "$unit" = vim4-kvm-hdmi ]; then echo inactive;
                else echo active; result=0; fi
            done
            return "$result"
        }
        '''
        def ssh(command):
            result = subprocess.run(['sh', '-c', fake_systemctl + command], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout)
            return result
        with patch.object(instance, 'ssh', side_effect=ssh) as remote:
            with self.assertRaisesRegex(RuntimeError, 'vim4-kvm-hdmi: inactive'):
                instance.check()
            self.assertEqual(remote.call_count, 1)
        self.assertNotIn('Smoke checks passed', instance.log.getvalue())

    def fixture(self, directory):
        raw = b'fake disk contents\0' * 100
        image = Path(directory) / 'candidate.img.xz'
        image.write_bytes(lzma.compress(raw))
        sidecar = image.with_suffix('.sha256')
        sidecar.write_text(hashlib.sha256(raw).hexdigest() + '  candidate.img\n')
        image.with_name('SHA256SUMS').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
            for p in (image, sidecar)))
        return image, raw

    def test_image_and_raw_checksums_before_board_access(self):
        with tempfile.TemporaryDirectory() as directory:
            image, raw = self.fixture(directory)
            self.assertEqual(board.image_metadata(image)[3], len(raw))
            image.write_bytes(image.read_bytes() + b'corrupt')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                board.image_metadata(image)

    def test_raw_checksum_sidecar_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image, _ = self.fixture(directory)
            image.with_suffix('.sha256').write_text('0' * 64 + ' candidate.img\n')
            with self.assertRaisesRegex(ValueError, 'sidecar'):
                board.image_metadata(image)

    def test_dry_run_never_contacts_board(self):
        with tempfile.TemporaryDirectory() as directory:
            image, _ = self.fixture(directory)
            with patch.object(board.subprocess, 'run', side_effect=AssertionError('hardware access')):
                board.main(['flash', '--exclusive', '--yes-erase-emmc', '--image', str(image),
                            '--serve-address', '192.168.50.2', '--dry-run'])

    def test_flash_requires_explicit_erasure_and_exclusivity(self):
        with patch.object(board.subprocess, 'run', side_effect=AssertionError('hardware access')):
            for args in (['flash'], ['flash', '--exclusive']):
                with self.assertRaises(SystemExit) as exc:
                    board.main(args)
                self.assertEqual(exc.exception.code, 2)

    def test_http_only_exposes_selected_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            image, _ = self.fixture(directory)
            with board.serve_image(image, '127.0.0.1') as url:
                with urllib.request.urlopen(url) as response:
                    self.assertEqual(response.read(), image.read_bytes())
                for path in ('/', '/SHA256SUMS', '/../SHA256SUMS'):
                    with self.assertRaises(urllib.error.HTTPError) as exc:
                        urllib.request.urlopen(url.rsplit('/', 1)[0] + path)
                    self.assertEqual(exc.exception.code, 404)
                    exc.exception.close()

    def test_failed_flash_never_reboots(self):
        instance = board.Board(SimpleNamespace(already_oowow=True, serve_address='127.0.0.1'), io.StringIO())
        with tempfile.TemporaryDirectory() as directory:
            image, _ = self.fixture(directory)
            for results in ([None, RuntimeError('write failed')], [None, None, RuntimeError('readback failed')]):
                with patch.object(instance, 'uart'), patch.object(instance, 'job', side_effect=results), patch.object(instance, 'run') as run:
                    with self.assertRaisesRegex(RuntimeError, 'failed'):
                        instance.flash(board.image_metadata(image))
                    run.assert_not_called()

    def test_background_timeout_does_not_restart_job(self):
        instance = board.Board(SimpleNamespace(), io.StringIO())
        with patch.object(instance, 'uart') as uart_call, patch.object(board.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(RuntimeError, 'may still be running'):
                instance.job('write-command', 'write', 10)
            launches = [call for call in uart_call.call_args_list if '.started' in call.args[0]]
            self.assertEqual(len(launches), 1)
            self.assertFalse(any('STATUS=' in call.args[0] for call in uart_call.call_args_list))

    def packages(self, directory, version='1.0~test1', component='all'):
        folder = Path(directory) / version
        folder.mkdir()
        components = {'all': board.COMPONENTS, 'pikvm': board.PIKVM_COMPONENTS,
                      'manager': ('vim4-manager',), 'onekvm': ('vim4-onekvm',)}[component]
        files = [folder / f'{name}_{version}_arm64.deb' for name in components]
        for path in files:
            path.write_bytes(path.name.encode())
        sources = folder / 'sources.json'
        sources.write_text(json.dumps({'component': component, 'sources': {'.': {'dirty': False}, 'NanoKVM-Pro': {'dirty': True}}}))
        (folder / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files + [sources]))
        return folder

    def test_package_set_validated_before_board_access(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self.packages(directory)
            version, debs, dirty = board.package_metadata(folder)
            self.assertEqual((version, len(debs), dirty), ('1.0~test1', len(board.COMPONENTS), ['NanoKVM-Pro']))
            debs[-1].write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'vim4-manager.*SHA256'):
                board.package_metadata(folder)
            debs[-1].unlink()
            with self.assertRaisesRegex(ValueError, 'vim4-manager'):
                board.package_metadata(folder)

    def test_pikvm_deployment_validates_its_complete_set(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self.packages(directory, component='pikvm')
            _, debs, _ = board.package_metadata(folder)
            debs[0].write_bytes(b'corrupt application')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                board.package_metadata(folder)

    def test_single_component_deployment_validates_checksum(self):
        for component in ('manager', 'onekvm'):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                folder = self.packages(directory, component=component)
                _, debs, _ = board.package_metadata(folder)
                self.assertEqual(len(debs), 1)
                debs[0].write_bytes(b'corrupt component')
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    board.package_metadata(folder)

    def test_deploy_requires_exclusivity_and_dry_run_is_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self.packages(directory)
            with patch.object(board.subprocess, 'run', side_effect=AssertionError('hardware access')):
                for args in (['deploy', '--packages', str(folder)], ['deploy', '--exclusive']):
                    with self.assertRaises(SystemExit) as exc, patch('sys.stderr', io.StringIO()):
                        board.main(args)
                    self.assertEqual(exc.exception.code, 2)
                board.main(['deploy', '--exclusive', '--packages', str(folder), '--dry-run'])

    def test_deploy_delegates_to_board_installer_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = board.package_metadata(self.packages(directory))
            instance = board.Board(SimpleNamespace(host='vim4'), io.StringIO())
            ssh_result = SimpleNamespace(stdout='/tmp/vim4-deploy.x\n', returncode=0)
            old = {name: '0.9' for name in board.COMPONENTS}
            with patch.object(instance, 'ssh', return_value=ssh_result), patch.object(instance, 'run') as run, \
                 patch.object(instance, 'sudo') as sudo, patch.object(instance, 'check') as check, \
                 patch.object(instance, 'installed_versions', side_effect=[old, old]):
                with self.assertRaisesRegex(RuntimeError, 'Installed versions differ'):
                    instance.deploy(metadata)
            check.assert_not_called()
            sudo.assert_called_once()
            self.assertIn('install-components.sh --exclusive /tmp/vim4-deploy.x', sudo.call_args.args[0])
            copied = run.call_args.args[0]
            self.assertTrue(any(path.endswith('tools/install-components.sh') for path in copied))
            self.assertTrue(any(path.endswith('SHA256SUMS') for path in copied))

    def test_sudo_password_never_reaches_command_stdin(self):
        instance = board.Board(SimpleNamespace(sudo_password_stdin=True), io.StringIO())
        with patch('sys.stdin', io.StringIO('secret\n')), patch.object(instance, 'ssh') as ssh:
            instance.sudo('true')
            instance.sudo('true')
        for call in ssh.call_args_list:
            self.assertTrue(call.args[0].startswith("sudo -k -S -p '' "))
            self.assertNotIn('secret', call.args[0])

    def test_dev_sudoers_is_valid_and_kept_out_of_packages(self):
        root = Path(__file__).resolve().parents[1]
        rule = root / 'board/vim4-dev-nopasswd.sudoers'
        if shutil.which('visudo'):
            subprocess.run(['visudo', '-cf', str(rule)], check=True, capture_output=True)
        packaging = (root / 'packaging/ubuntu/package.py').read_text() + (root / 'packaging/image/configure.sh').read_text()
        self.assertNotIn('nopasswd', packaging.lower())

    def test_enroll_verifies_passwordless_sudo(self):
        instance = board.Board(SimpleNamespace(host='vim4'), io.StringIO())
        ssh_result = SimpleNamespace(stdout='/tmp/vim4-enroll.x\n', returncode=0)
        with patch.object(instance, 'ssh', return_value=ssh_result) as ssh, patch.object(instance, 'run'), \
             patch.object(instance, 'sudo') as sudo:
            instance.enroll()
        self.assertIn('visudo -cf', sudo.call_args.args[0])
        self.assertIn(unittest.mock.call('sudo -n true'), ssh.call_args_list)

    def test_subprocesses_never_consume_piped_password(self):
        instance = board.Board(SimpleNamespace(), io.StringIO())
        with patch.object(board.subprocess, 'run', return_value=SimpleNamespace(stdout='', returncode=0)) as run:
            instance.run(['ssh', 'vim4', 'true'])
            self.assertIs(run.call_args.kwargs['stdin'], board.subprocess.DEVNULL)
            instance.run(['ssh', 'vim4', 'sudo -S true'], input_text='secret\n')
            self.assertIsNone(run.call_args.kwargs['stdin'])

    def test_absolute_report_matches_gadget_descriptor(self):
        self.assertEqual(board.absolute_report(0, 1), bytes([0, 0, 0, 0xff, 0x7f, 0]))
        self.assertEqual(board.absolute_report(-1, 2)[1:5], bytes([0, 0, 0xff, 0x7f]))
        self.assertEqual(len(board.absolute_report(0.5, 0.5)), 6)

    def hid_board(self):
        instance = board.Board(SimpleNamespace(host='vim4'), io.StringIO())
        attached = SimpleNamespace(stdout='"idProduct" = 260\n')
        return instance, patch.object(board.subprocess, 'run', return_value=attached)

    def test_hid_mismatch_fails_and_restores_cursor(self):
        instance, ioreg = self.hid_board()
        with ioreg, patch.object(board, 'host_pointer', side_effect=[(0.5, 0.5), (0.9, 0.9)]), \
             patch.object(board.time, 'sleep'), patch.object(instance, 'ssh') as ssh:
            status, _ = instance.verify_hid()
        self.assertEqual(status, 'FAIL')
        self.assertIn(''.join(f'\\{b:03o}' for b in board.absolute_report(0.5, 0.5)), ssh.call_args.args[0])

    def test_verify_reports_skip_without_failing(self):
        instance = board.Board(SimpleNamespace(log_dir=Path(tempfile.mkdtemp())), io.StringIO())
        with patch.object(instance, 'check'), \
             patch.object(instance, 'verify_hid', return_value=('SKIP', 'not attached')), \
             patch.object(instance, 'verify_audio', return_value=('PASS', 'ok')), \
             patch.object(instance, 'verify_video', return_value=('PASS', 'ok')):
            instance.verify()
        with patch.object(instance, 'check'), \
             patch.object(instance, 'verify_hid', side_effect=RuntimeError('ssh dropped')), \
             patch.object(instance, 'verify_audio', return_value=('PASS', 'ok')), \
             patch.object(instance, 'verify_video', return_value=('PASS', 'ok')):
            with self.assertRaisesRegex(RuntimeError, 'Functional verification failed'):
                instance.verify()
        self.assertIn('ssh dropped', (instance.args.log_dir / 'verify.json').read_text())

    def test_audio_busy_pipeline_is_skipped_but_empty_capture_fails(self):
        instance = board.Board(SimpleNamespace(host='vim4'), io.StringIO())
        for output, expected in [
            ('arecord: audio open error: Device or resource busy\n0 0\n', 'SKIP'),
            ('0 0\n', 'FAIL'),
            ('48000 0\n', 'PASS'),
        ]:
            with self.subTest(output=output), patch.object(instance, 'ssh',
                    return_value=SimpleNamespace(returncode=0, stdout=output)):
                self.assertEqual(instance.verify_audio()[0], expected)

    def provision_board(self, directory, key_works):
        key = Path(directory) / 'id_test'
        key.with_suffix('.pub').write_text('ssh-ed25519 AAAATEST dev\n')
        instance = board.Board(SimpleNamespace(host='vim4', sudo_password_stdin=False), io.StringIO())
        config = {'hostname': '192.0.2.10', 'user': 'khadas', 'identityfile': str(key)}
        results = iter(key_works)
        ssh = lambda command, check=True, **_: SimpleNamespace(returncode=0 if next(results) else 255, stdout='')
        return instance, config, ssh

    def test_provision_uses_password_once_then_enrolls(self):
        with tempfile.TemporaryDirectory() as directory:
            # true fails, then succeeds after key install; sudo -n fails.
            instance, config, ssh = self.provision_board(directory, [False, True, False])
            with patch.object(instance, 'ssh_config', return_value=config), \
                 patch.object(board.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                 patch.object(instance, 'ssh', side_effect=ssh), patch.object(instance, 'run') as run, \
                 patch.object(instance, 'enroll') as enroll:
                instance.provision(replace_host_key=True)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0], ['ssh-keygen', '-R', '192.0.2.10'])
            login = commands[1]
            self.assertIn('khadas@192.0.2.10', login)
            self.assertIn('StrictHostKeyChecking=accept-new', login)
            self.assertNotIn('khadas\n', ' '.join(login))
            self.assertEqual(run.call_args_list[1].kwargs['env']['VIM4_PASSWORD'], 'khadas')
            self.assertIn('ssh-ed25519 AAAATEST dev', login[-1])
            enroll.assert_called_once()
            self.assertEqual(instance.password, 'khadas\n')

    def test_provision_is_noop_on_enrolled_board(self):
        with tempfile.TemporaryDirectory() as directory:
            instance, config, ssh = self.provision_board(directory, [True, True])
            with patch.object(instance, 'ssh_config', return_value=config), \
                 patch.object(board.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                 patch.object(instance, 'ssh', side_effect=ssh), patch.object(instance, 'run') as run, \
                 patch.object(instance, 'enroll') as enroll:
                instance.provision()
            run.assert_not_called()
            enroll.assert_not_called()

    def test_flash_provisions_after_verified_boot(self):
        instance = board.Board(SimpleNamespace(already_oowow=True, serve_address='127.0.0.1',
                                               device='/dev/null', log_dir=Path('/tmp')), io.StringIO())
        with tempfile.TemporaryDirectory() as directory:
            image, _ = self.fixture(directory)
            with patch.object(instance, 'uart'), patch.object(instance, 'job'), patch.object(instance, 'run'), \
                 patch.object(instance, 'provision') as provision, patch.object(instance, 'check') as check:
                instance.flash(board.image_metadata(image))
            provision.assert_called_once_with(replace_host_key=True)
            check.assert_called_once()

    def test_long_job_commands_are_uploaded_in_short_lines(self):
        instance = board.Board(SimpleNamespace(), io.StringIO())
        command = 'curl -o /tmp/x "http://192.0.2.1/' + 'a' * 700 + '" && echo "done"'
        sent = []
        def uart(line):
            sent.append(line)
            return 'STATUS=0' if 'STATUS=' in line else ''
        with patch.object(instance, 'uart', side_effect=uart):
            instance.job(command, 'download', 60)
        self.assertTrue(all(len(line) < 300 for line in sent), max(map(len, sent)))
        chunks = [line for line in sent if line.startswith("printf '%s'")]
        payload = ''.join(line.split()[2] for line in sorted(chunks, key=lambda line: line.rsplit('.', 1)[1]))
        script = base64.b64decode(payload)
        self.assertIn(command.encode(), script)
        self.assertTrue(any(hashlib.sha256(script).hexdigest() in line for line in sent))
        # The uploaded wrapper must run the command and record its status.
        with tempfile.TemporaryDirectory() as directory:
            job = next(line for line in sent if '.started' in line).split()[2].removesuffix('.started')
            wrapper = script.decode().replace(job, directory + '/job').replace(command, 'exit 3')
            subprocess.run(['sh', '-c', wrapper], check=True)
            self.assertEqual(Path(directory, 'job.done').read_text().strip(), '3')

    def test_corrupted_uart_reply_is_retried_without_relaunch(self):
        instance = board.Board(SimpleNamespace(), io.StringIO())
        sent = []
        def uart(line):
            sent.append(line)
            # Each command's first reply is lost, as observed on OOWOW.
            if sent.count(line) == 1:
                raise RuntimeError('Command failed (124); see log')
            return 'STATUS=0' if 'STATUS=' in line else ''
        with patch.object(instance, 'uart', side_effect=uart), patch.object(board.time, 'sleep'):
            instance.job('true', 'probe', 60)
        launches = [line for line in sent if '.started' in line]
        self.assertTrue(launches)
        self.assertTrue(all(line.startswith('test -e ') for line in launches))

    def test_uart_status_and_missing_completion(self):
        self.assertEqual(uart.parse_result('echo command\r\nBEGIN\r\nfailed\r\nDONE:7\r\n', 'BEGIN', 'DONE'), ('failed', 7))
        with self.assertRaises(TimeoutError):
            uart.parse_result('BEGIN\r\nstill running', 'BEGIN', 'DONE')

    def test_uart_does_not_stop_at_echoed_marker(self):
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"echo DONE:%s\r\nBEGIN\r\nOK\r\nDONE:0\r\n")
            output = uart.read_result(read_fd, 'DONE', 1)
            self.assertEqual(uart.parse_result(output.decode(), 'BEGIN', 'DONE'), ('OK', 0))
        finally:
            os.close(read_fd)
            os.close(write_fd)


if __name__ == '__main__':
    unittest.main()
