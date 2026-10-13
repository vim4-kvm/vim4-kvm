"""Offline safety boundaries; no board, SSH, sudo or device writes."""
import hashlib
import importlib.util
import io
import lzma
import os
import subprocess
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
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
            self.assertEqual(uart_call.call_count, 1)

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
