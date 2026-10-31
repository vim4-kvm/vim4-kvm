"""ASoC PCM owner using the reviewed generic ALSA wrapper installed by manager.

No vendor mixer routing is imported or called. This temporary packaging
dependency should converge to one common ALSA module shared by both providers.
Device selection/ELD qualification belongs to the controller, never to this pump.
"""
import ctypes
import importlib.util

from .audio import PCMPeriod


def installed_pcm(path='/usr/libexec/vim4_passthrough_audio.py'):
    spec = importlib.util.spec_from_file_location('passthrough_alsa_backend', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PCM()


class AlsaPump:
    def __init__(self, owner, pcm, capture_device, playback_device):
        if owner.rate is None:
            raise ValueError('Qualify rate before opening PCM')
        self.owner, self.pcm, self.sequence = owner, pcm, 0
        try:
            self.rx = pcm.acquire(capture_device.encode(), 1)
            self.tx = pcm.acquire(playback_device.encode(), 0)
            pcm.configure(self.rx, 1, owner.rate)
            pcm.configure(self.tx, 0, owner.rate)
            pcm.write(self.tx, (ctypes.c_short * 3072)(), 1536)
            owner.enable_tx(True)
        except BaseException:
            pcm.close()
            raise

    def step(self):
        self.pcm.maintain_playback(self.tx)
        samples = (ctypes.c_short * 512)()
        count = self.pcm.read(self.rx, samples)  # wrapper recovers RX in place
        self.owner.capture_xruns = self.pcm.capture_xruns
        if count not in (0, 256):
            raise OSError('Partial RX period requires source requalification')
        if count:
            self.owner.feed(PCMPeriod(self.owner.generation, self.sequence,
                                      self.owner.rate, bytes(samples)))
            self.sequence += 1
        data = self.owner.take_tx()
        self.pcm.write(self.tx, (ctypes.c_short * 512).from_buffer_copy(data), 256)

    def close(self):
        self.owner.enable_tx(False)
        self.pcm.drop()
        self.pcm.close()
