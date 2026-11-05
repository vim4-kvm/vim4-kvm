import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('continuous_uart', Path(__file__).resolve().parents[1]/'tools/board_uart.py')
uart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uart)


class ContinuousUARTTests(unittest.TestCase):
    def test_split_reset_and_kernel_warning_are_not_confused_with_log_messages(self):
        events = uart.BootEvents('trial')
        for data in (b'Lin', b'ux version trial kernel\n[ADLAK WARN] ordinary log\n', b'T7:B', b'L: cold_boot\n'):
            events.feed(data, 123)
        self.assertEqual(events.linux_started, 123)
        self.assertIsInstance(events.error, uart.ColdBootReset)
        for signature in (b'BUG: fault', b'[    4.200] BUG: fault',
                          b'WARNING: CPU: 0 PID: 123', b'------------[ cut here ]------------',
                          b'Kernel panic - not syncing', b'Internal error: Oops',
                          b'Unable to handle kernel', b'BUG: KASAN:'):
            events = uart.BootEvents('trial')
            events.feed(b'Linux version trial\n'+signature[:2], 1)
            events.feed(signature[2:]+b' real kernel failure\n', 2)
            self.assertIsInstance(events.error, RuntimeError)
            self.assertNotIsInstance(events.error, uart.ColdBootReset)

    def test_userspace_warning_and_embedded_bug_word_are_not_kernel_failures(self):
        events = uart.BootEvents('trial')
        events.feed(b'Linux version trial\nsystemd: WARNING: unit not found\n'
                    b'WARNING: deprecated option\nhelper: BUG: report this message\n', 1)
        self.assertIsNone(events.error)

    def test_recovery_replays_original_chunk_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, writer = socket.socketpair()
            try:
                with uart.ContinuousUART(reader.fileno(), directory) as stream:
                    stream.arm('trial')
                    with stream.condition:
                        stream.events.feed(b'Linux version trial\nT7:BL: reset\nLinux ver', 111)
                        stream.events.feed(b'sion formal\n', 222)
                        stream.recovery('formal')
                    self.assertEqual(stream.events.linux_started, 222)
            finally:
                reader.close(); writer.close()

    def test_wrong_kernel_and_repeated_linux_boot_cannot_pass(self):
        events = uart.BootEvents('trial')
        events.feed(b'Linux version other\n', 1)
        self.assertIsInstance(events.error, RuntimeError)
        events = uart.BootEvents('trial')
        events.feed(b'Linux version trial\nLinux version trial\n', 1)
        self.assertIsInstance(events.error, uart.ColdBootReset)

    def test_final_recovery_retains_failure_and_cannot_resume_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, writer = socket.socketpair()
            try:
                with uart.ContinuousUART(reader.fileno(), directory) as stream:
                    stream.arm('trial')
                    stream.events.feed(b'BUG: failure\n', 1)
                    stream.final_recovery('formal')
                    with self.assertRaisesRegex(RuntimeError, 'another sample'):
                        stream.begin_sample('B2')
                    with self.assertRaisesRegex(RuntimeError, 'another candidate'):
                        stream.arm('trial')
                    stream.arm('formal')
                records = (Path(directory)/'uart-chunks.jsonl').read_text()
                self.assertIn('BUG: failure', records)
            finally:
                reader.close(); writer.close()

    def test_entry_warning_stops_before_first_requested_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, writer = socket.socketpair()
            try:
                with self.assertRaisesRegex(RuntimeError, 'Kernel failure'):
                    with uart.ContinuousUART(reader.fileno(), directory) as stream:
                        stream.observe_running('formal')
                        writer.sendall(b'[ 40.1] WARNING: CPU: 0 PID: 42\n')
                        stream.read_since(0, 2)
                records = (Path(directory)/'uart-chunks.jsonl').read_text()
                self.assertNotIn('requested-boot', records)
            finally:
                reader.close(); writer.close()

    def test_real_stream_continues_past_login_and_preserves_rx_tx_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            # socketpair exercises the real reader and condition coordination,
            # with no timing sleeps or mocked select/read loop.
            reader, writer = socket.socketpair()
            try:
                with uart.ContinuousUART(reader.fileno(), directory) as stream:
                    cursor = stream.arm('trial')
                    writer.sendall(b'Linux version trial\nlogin:\n')
                    cursor, data = stream.read_since(cursor, 2)
                    self.assertIn(b'login:', data)
                    stream.send(b'probe\n')
                    self.assertEqual(writer.recv(6), b'probe\n')
                    writer.sendall(b'after login\n')
                    cursor, data = stream.read_since(cursor, 2)
                    self.assertEqual(data, b'after login\n')
                    stream.arm('formal')  # Explicit next requested reboot.
                    writer.sendall(b'T7:BL: normal reboot\nLinux version formal\n')
                    stream.read_since(cursor, 2)
                    stream.check()
                raw = (Path(directory)/'uart.raw').read_bytes()
                chunks = [json.loads(line) for line in (Path(directory)/'uart-chunks.jsonl').read_text().splitlines()]
                previous = 0
                for chunk in chunks:
                    self.assertEqual(chunk['offset'], previous)
                    previous += chunk['length']
                    self.assertGreater(chunk['utc_ns'], 0)
                    self.assertGreater(chunk['monotonic_ns'], 0)
                self.assertEqual(previous, len(raw))
                self.assertIn(b'after login', raw)
            finally:
                reader.close(); writer.close()

    def test_recovery_banner_in_same_chunk_is_retained_and_second_failure_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, writer = socket.socketpair()
            try:
                with self.assertRaises(uart.ColdBootReset):
                    with uart.ContinuousUART(reader.fileno(), directory) as stream:
                        cursor = stream.arm('trial')
                        writer.sendall(b'Linux version trial\nT7:BL: reset\nLinux version formal\n')
                        with self.assertRaises(uart.ColdBootReset):
                            stream.read_since(cursor, 2)
                        stream.recovery('formal')
                        self.assertIsNotNone(stream.events.linux_started)
                        cursor = len(stream.data)
                        writer.sendall(b'T7:BL: second reset\n')
                        with self.assertRaises(uart.ColdBootReset):
                            stream.read_since(cursor, 2)
                        with self.assertRaisesRegex(RuntimeError, 'Only an observed'):
                            stream.recovery('formal')
                        stream.check()
            finally:
                reader.close(); writer.close()

    def test_disconnection_is_an_error_not_successful_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            reader, writer = socket.socketpair()
            try:
                with self.assertRaisesRegex(RuntimeError, 'reader failed'):
                    with uart.ContinuousUART(reader.fileno(), directory) as stream:
                        writer.close()
                        stream.read_since(0, 2)
            finally:
                reader.close(); writer.close()
