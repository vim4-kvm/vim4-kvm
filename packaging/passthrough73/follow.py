"""Output intent qualification; copied timing rules match the 5.15 provider.

Events invalidate observations, never reset RX/EDID. The caller supplies sink
modes and real input timings and performs TEST_ONLY before committing an intent.
"""
from collections import deque
from statistics import median


class Follow:
    def __init__(self):
        self.samples = deque(maxlen=7)
        self.current = None
        self.pending = None
        self.since = None
        self.geometry = None

    def observe(self, width, height, hz, sink, modes, now):
        if (width, height) != self.geometry:
            self.samples.clear()
            self.geometry = width, height
        self.samples.append(hz)
        rate = median(self.samples)
        nominal, fractional = min(((n, f) for n in (24, 25, 30, 50, 60)
                                   for f in ((False, True) if n in (24, 30, 60) else (False,))),
                                  key=lambda item: abs(rate - item[0] / (1.001 if item[1] else 1)))
        midpoint = (nominal + nominal / 1.001) / 2
        if self.current and self.current[2] == nominal and abs(rate - midpoint) <= .005:
            fractional = self.current[3]
        if abs(rate - nominal / (1.001 if fractional else 1)) > .2:
            self.pending = self.since = None
            raise ValueError('Unqualified input refresh rate')
        intent = (width, height, nominal, fractional, sink)
        if (width, height, nominal, fractional) not in modes:
            self.pending = self.since = None
            raise ValueError('No 1:1 sink mode for input timing')
        if intent == self.current:
            self.pending = self.since = None
            return None
        if intent != self.pending:
            self.pending, self.since = intent, now
            return None
        return intent if now - self.since >= 2 else None

    def committed(self, intent):
        if intent != self.pending:
            raise ValueError('Stale output intent')
        self.current, self.pending, self.since = intent, None, None

    def disconnected(self):
        self.current = self.pending = self.since = None
        self.samples.clear()
        self.geometry = None


def hdr_output(prefer_hdr, pixel_eotf, source_eotf, mapped, sink_eotfs):
    """Return the actual output EOTF and mapping fact, never infer from preference.

    HDR2 mapping is supplied by driver readback. No GPU/VD1 tonemapper is implied.
    """
    if mapped:
        if pixel_eotf != 'SDR' or source_eotf not in ('PQ', 'HLG'):
            raise ValueError('Contradictory mapping readback')
        if prefer_hdr and source_eotf in sink_eotfs:
            raise ValueError('Original high-bit-depth HDR pixels are unavailable')
        return 'SDR', True
    if pixel_eotf != source_eotf:
        raise ValueError('Pixel domain does not match source; no mapping fact')
    if source_eotf == 'SDR':
        return 'SDR', False
    if prefer_hdr and source_eotf in sink_eotfs:
        return source_eotf, False
    raise ValueError('A real HDR-to-SDR mapping path is required')
