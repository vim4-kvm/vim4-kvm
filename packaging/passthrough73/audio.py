"""Application-independent PCM fanout; ALSA device adapters are not supplied yet.

Exactly one owner feeds completed RX periods into this object. TX uses its own
bounded queue; an absent remote subscriber never stops RX or local TX. The ALSA
adapter must keep TX running on starvation and recover RX xruns in place.
"""
from collections import deque
from dataclasses import dataclass
import errno


@dataclass(frozen=True)
class PCMPeriod:
    generation: int
    sequence: int
    rate: int
    data: bytes


class AudioOwner:
    def __init__(self, period_frames=256, queue_periods=8):
        if period_frames < 1 or queue_periods < 1:
            raise ValueError('Audio period and queue must be positive')
        self.period_frames, self.queue_periods = period_frames, queue_periods
        self.subscribers = {}
        self.dropped_periods = {}
        self.tx = deque()
        self.tx_enabled = False
        self.tx_gap_frames = 0
        self.capture_xruns = 0
        self.generation = None
        self.rate = None

    def configure_source(self, generation, rate):
        if rate not in (44100, 48000):
            raise ValueError('Only stereo S16_LE 44.1/48k PCM is qualified by this contract')
        if self.generation is not None and generation <= self.generation:
            raise ValueError('Audio generation must advance')
        self.generation, self.rate = generation, rate
        self.tx.clear()
        for queue in self.subscribers.values():
            queue.clear()

    def subscribe(self, name):
        if name in self.subscribers:
            raise ValueError('Audio subscriber already registered')
        self.subscribers[name] = deque()
        self.dropped_periods[name] = 0

    def disconnect(self, name):
        del self.subscribers[name]
        del self.dropped_periods[name]

    def enable_tx(self, enabled):
        self.tx_enabled = bool(enabled)
        self.tx.clear()

    def recover_capture(self, error, recover):
        """Recover the existing RX handle; the callback never receives TX.

        recover is the adapter's snd_pcm_recover(bound_RX, error, silent=1).
        TX starvation continues through take_tx's silence periods.
        """
        if error in (-errno.EAGAIN, -errno.EINTR):
            return False
        if error not in (-errno.EPIPE, -getattr(errno, 'ESTRPIPE', 86)):
            raise OSError(-error, 'RX PCM operation failed')
        result = recover(error, 1)
        if result < 0:
            raise OSError(-result, 'RX PCM recovery failed')
        self.capture_xruns += 1
        return True

    def feed(self, period):
        if (period.generation, period.rate) != (self.generation, self.rate):
            raise ValueError('Stale or unqualified PCM period')
        if len(period.data) != self.period_frames * 2 * 2:
            raise ValueError('Expected one stereo S16_LE period')
        for name, queue in self.subscribers.items():
            if len(queue) == self.queue_periods:
                queue.popleft()
                self.dropped_periods[name] += 1
            queue.append(period)
        if self.tx_enabled:
            if len(self.tx) == self.queue_periods:
                self.tx.popleft()
            self.tx.append(period)

    def take(self, name):
        queue = self.subscribers[name]
        return queue.popleft() if queue else None

    def take_tx(self):
        """One TX period, or silence; adapter must not reprepare TX for a gap."""
        if not self.tx_enabled or self.rate is None:
            return None
        if self.tx:
            return self.tx.popleft().data
        self.tx_gap_frames += self.period_frames
        return bytes(self.period_frames * 2 * 2)
