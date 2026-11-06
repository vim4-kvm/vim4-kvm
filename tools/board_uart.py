"""Opt-in continuous UART evidence for a batch of RAM boots.

The caller owns the board lease and explicitly supplies an already opened port.
One reader retains raw bytes across boot(), ready checks and recovery. This
module never opens a port, reboots a host or interprets silence as success.
"""
import json
import os
from pathlib import Path
import re
import select
import threading
import time


class ColdBootReset(RuntimeError):
    """An observed Linux boot returned to ROM without a requested reboot."""


class BootEvents:
    failure = re.compile(
        rb'WARNING: CPU: \d+ PID: \d+|------------\[ cut here \]------------|'
        rb'^(?:\[\s*\d+(?:\.\d+)?\]\s*)?BUG: |'
        rb'Kernel panic -|Internal error: Oops|Unable to handle kernel|'
        rb'WARNING: possible circular locking dependency detected')

    def __init__(self, release):
        self.release = release
        self.linux_started = None
        self.observed_release = None
        self.error = None
        self.tail = b''
        self.after_reset = []
        self.reset_at = None

    def feed(self, data, monotonic_ns):
        if isinstance(self.error, ColdBootReset):
            self.after_reset.append((monotonic_ns, data))
            return
        lines = (self.tail + data).split(b'\n')
        self.tail = lines.pop()
        if len(self.tail) > 65536:
            self.error = RuntimeError('UART line exceeds evidence parser limit')
            self.tail = b''
        for number, line in enumerate(lines):
            if self.error is not None:
                return
            if self.failure.search(line):
                self.error = RuntimeError('Kernel failure in UART: ' + line.decode(errors='replace'))
                return
            match = re.search(rb'Linux version (\S+)', line)
            booting = b'Booting Linux' in line
            if match or booting:
                # A normal boot emits both banners; either survives a dropped
                # serial chunk. A repeated banner means another Linux start.
                repeated = (booting and self.linux_started is not None) or (match and self.observed_release is not None)
                if repeated:
                    self.error = ColdBootReset('A second Linux boot followed the selected candidate')
                else:
                    if self.linux_started is None:
                        self.linux_started = monotonic_ns
                    if match:
                        self.observed_release = match[1].decode(errors='replace')
            elif self.linux_started is not None and b'T7:BL:' in line:
                self.error = ColdBootReset('Selected Linux returned to T7 ROM')
            if isinstance(self.error, ColdBootReset):
                self.reset_at = monotonic_ns
                # A ROM marker and the recovery banner may share one USB read.
                remaining = b''.join(part + b'\n' for part in lines[number + 1:]) + self.tail
                if match or booting:
                    remaining = line + b'\n' + remaining
                self.after_reset = [(monotonic_ns, remaining)]
                self.tail = b''
                return


class ContinuousUART:
    def __init__(self, fd, directory):
        self.fd = fd
        directory = Path(directory)
        self.raw = (directory / 'uart.raw').open('xb')
        try:
            self.index = (directory / 'uart-chunks.jsonl').open('x')
        except BaseException:
            self.raw.close()
            raise
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.data = bytearray()
        self.offset = 0
        self.error = None
        self.events = None
        self.sample = None
        self.recovering = False
        self.final_target = None
        self.thread = threading.Thread(target=self._read, name='board-uart', daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def _record(self, direction, data=b'', **fields):
        stamp = dict(utc_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(),
                     direction=direction, offset=self.offset, length=len(data), sample=self.sample, **fields)
        self.raw.write(data)
        self.raw.flush()
        self.offset += len(data)
        self.index.write(json.dumps(stamp) + '\n')
        self.index.flush()
        return stamp

    def mark(self, event, **fields):
        with self.condition:
            self._record('event', event=event, **fields)

    def begin_sample(self, sample):
        with self.condition:
            self.check()
            if self.final_target is not None:
                raise RuntimeError('Final recovery cannot start another sample')
            self.sample = sample
            self._record('event', event='sample-start')

    def observe_running(self, release):
        """Check entry-phase kernel faults without claiming a requested reboot."""
        with self.condition:
            self.check()
            self.events = BootEvents(release)
            self._record('event', event='observe-running', release=release)

    def arm(self, release):
        """Explicit boundary before a requested reboot; no automatic retries."""
        with self.condition:
            self.check()
            if self.final_target is not None and release != self.final_target:
                raise RuntimeError('Final recovery cannot select another candidate')
            self.events = BootEvents(release)
            self.recovering = False
            self._record('event', event='requested-boot', release=release)
            return len(self.data)

    def final_recovery(self, release):
        """Stop sampling permanently; retain the failure before normal recovery."""
        with self.condition:
            if self.error is not None:
                self.check()
            self._record('event', event='final-recovery', release=release,
                         previous_error=str(self.events.error) if self.events else None)
            self.final_target = release
            self.events = None

    def check(self):
        if self.error is not None:
            raise RuntimeError('Continuous UART reader failed') from self.error
        if self.events is not None and self.events.error is not None:
            raise self.events.error

    def cold_reset(self):
        return self.events is not None and isinstance(self.events.error, ColdBootReset)

    def recovery(self, release):
        """Caller acknowledges a cold reset, then monitors the default boot."""
        with self.condition:
            if self.recovering or self.events is None or not isinstance(self.events.error, ColdBootReset):
                raise RuntimeError('Only an observed cold reset can enter automatic recovery')
            pending = self.events.after_reset
            self.events = BootEvents(release)
            self.recovering = True
            for stamp, data in pending:
                self.events.feed(data, stamp)
            self._record('event', event='automatic-recovery', release=release)
            self.check()

    def send(self, data):
        with self.condition:
            self.check()
            while data:
                written = os.write(self.fd, data)
                if written <= 0:
                    raise OSError('UART write made no progress')
                self._record('tx', data[:written])
                data = data[written:]

    def read_since(self, cursor, timeout):
        with self.condition:
            if cursor > len(self.data):
                raise ValueError('UART cursor is beyond received data')
            self.condition.wait_for(lambda: len(self.data) > cursor or self.error is not None,
                                    timeout=timeout)
            self.check()
            return len(self.data), bytes(self.data[cursor:])

    def _read(self):
        try:
            while not self.stop.is_set():
                if not select.select([self.fd], [], [], .1)[0]:
                    continue
                data = os.read(self.fd, 65536)
                if not data:
                    raise EOFError('UART disconnected')
                with self.condition:
                    stamp = self._record('rx', data)
                    self.data.extend(data)
                    if self.events is not None:
                        self.events.feed(data, stamp['monotonic_ns'])
                    self.condition.notify_all()
        except BaseException as error:
            with self.condition:
                self.error = error
                self.condition.notify_all()

    def __exit__(self, kind, value, traceback):
        self.stop.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise RuntimeError('UART reader did not stop; retain port ownership')
        self.raw.close()
        self.index.close()
        # Port lifetime belongs to the caller, including failed context entry.
        if kind is None:
            self.check()
