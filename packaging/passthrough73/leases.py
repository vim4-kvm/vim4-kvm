"""Frame ownership for an application-independent V4L2/DRM broker.

All methods run on one event loop. Adapters retain the exported DMA-buf fds,
publish only completed DQBUF frames, and drain recyclable buffer keys before
QBUF. No fd ownership or hardware access is implemented here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Buffer:
    index: int
    dmabuf_fd: int
    allocation_size: int


@dataclass(frozen=True)
class Frame:
    generation: int
    index: int
    sequence: int
    timestamp_ns: int
    width: int
    height: int
    pitch: int
    uv_offset: int
    colorspace: str
    quantization: str

    @property
    def key(self):
        return self.generation, self.index


@dataclass(frozen=True)
class Lease:
    token: int
    consumer: int
    frame: Frame


@dataclass
class _Consumer:
    name: str
    limit: int
    pending: Frame | None = None
    active: int = 0
    connected: bool = True


class FrameBroker:
    """Bounded latest-frame distribution with explicit hardware retirement.

    Taking a frame transfers a pending reference into an in-flight lease.
    Disconnect drops only pending frames. In-flight frames remain pinned until
    the adapter reports actual reader retirement (not page-flip/latch alone).
    """

    def __init__(self, budget_bytes=192 * 1024 * 1024, capture_reserve=2):
        if budget_bytes <= 0 or capture_reserve < 1:
            raise ValueError('Require a positive memory budget and capture reserve')
        self.budget_bytes = budget_bytes
        self.capture_reserve = capture_reserve
        self.generation = None
        self.accepting = False
        self.buffers = {}
        self._consumers = {}
        self._frames = {}
        self._references = {}
        self._leases = {}
        self._pinned = set()
        self._recyclable = []
        self._next_consumer = 0
        self._next_lease = 0

    def begin_generation(self, generation, buffers):
        if self.accepting or self._frames or self._recyclable:
            raise RuntimeError('Stop and retire the previous pool before starting another')
        if self.generation is not None and generation <= self.generation:
            raise ValueError('Generation must advance')
        buffers = list(buffers)
        if not buffers or any(b.index < 0 or b.dmabuf_fd < 0 or b.allocation_size <= 0
                              for b in buffers):
            raise ValueError('Require a nonempty exported buffer pool')
        if len({b.index for b in buffers}) != len(buffers):
            raise ValueError('Duplicate capture buffer index')
        if sum(b.allocation_size for b in buffers) > self.budget_bytes:
            raise ValueError('Capture pool exceeds the shared memory budget')
        if self._reserved_slots() + self.capture_reserve > len(buffers):
            raise ValueError('Pool cannot cover consumer leases and capture working slots')
        self.buffers = {b.index: b for b in buffers}
        self.generation = generation
        self.accepting = True

    def subscribe(self, name, in_flight_limit):
        if in_flight_limit < 1:
            raise ValueError('Consumer requires a positive in-flight limit')
        if self.buffers and self._reserved_slots() + in_flight_limit + 1 + \
                self.capture_reserve > len(self.buffers):
            raise ValueError('Consumer would consume reserved capture working slots')
        self._next_consumer += 1
        self._consumers[self._next_consumer] = _Consumer(name, in_flight_limit)
        return self._next_consumer

    def disconnect(self, consumer):
        state = self._consumers[consumer]
        if not state.connected:
            raise ValueError('Consumer already disconnected')
        state.connected = False
        if state.pending is not None:
            pending, state.pending = state.pending, None
            self._release(pending)
        if not state.active:
            del self._consumers[consumer]

    def publish(self, frame):
        if not self.accepting or frame.generation != self.generation:
            raise ValueError('Frame does not belong to the running generation')
        if frame.index not in self.buffers:
            raise ValueError('Frame is outside the capture pool')
        if frame.key in self._frames or frame.key in self._recyclable:
            raise RuntimeError('Capture reused a buffer before all readers retired')
        self._frames[frame.key] = frame
        # The publication reference prevents a replaced pending frame from
        # recycling this frame while subscribers are being visited.
        self._references[frame.key] = 1
        for state in self._consumers.values():
            if not state.connected:
                continue
            if state.pending is not None:
                self._release(state.pending)
            state.pending = frame
            self._references[frame.key] += 1
        self._release(frame)

    def take(self, consumer):
        state = self._consumers[consumer]
        if not state.connected:
            raise ValueError('Consumer disconnected')
        if state.pending is None or state.active >= state.limit:
            return None
        frame, state.pending = state.pending, None
        state.active += 1
        self._next_lease += 1
        lease = Lease(self._next_lease, consumer, frame)
        self._leases[lease.token] = lease
        return lease

    def retire(self, lease):
        if self._leases.get(lease.token) != lease:
            raise ValueError('Unknown or already retired lease')
        if lease.token in self._pinned:
            raise RuntimeError('Hardware fault pinned this lease until reboot')
        del self._leases[lease.token]
        state = self._consumers[lease.consumer]
        state.active -= 1
        self._release(lease.frame)
        if not state.connected and not state.active:
            del self._consumers[lease.consumer]

    def pin_fault(self, lease):
        if self._leases.get(lease.token) != lease:
            raise ValueError('Unknown or already retired lease')
        self._pinned.add(lease.token)

    def stop_generation(self):
        """Stop distribution; adapters must separately stop capture and readers."""
        self.accepting = False
        for state in self._consumers.values():
            if state.pending is not None:
                pending, state.pending = state.pending, None
                self._release(pending)

    def take_recyclable(self):
        """Transfer safe buffer keys to the adapter, preserving old generation IDs.

        The adapter QBUFs only into that generation's still-running queue. After
        STREAMOFF it instead releases that pool's buffers; never QBUF an old key
        into the current capture fd.
        """
        keys, self._recyclable = self._recyclable, []
        return keys

    def _release(self, frame):
        self._references[frame.key] -= 1
        if self._references[frame.key] == 0:
            del self._references[frame.key]
            del self._frames[frame.key]
            self._recyclable.append(frame.key)

    def _reserved_slots(self):
        # Independent latest-pending and in-flight ownership is a conservative
        # upper bound; sharing the same frame only reduces actual occupancy.
        return sum(s.limit + 1 if s.connected else s.active for s in self._consumers.values())

    def occupancy(self):
        return {'retained_buffers': len(self._frames),
                'pending_recycle': len(self._recyclable),
                'in_flight_leases': len(self._leases),
                'pinned_leases': len(self._pinned),
                'pending_consumers': sum(s.pending is not None for s in self._consumers.values())}
