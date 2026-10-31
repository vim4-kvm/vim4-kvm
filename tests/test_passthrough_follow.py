import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
from passthrough73.follow import Follow, hdr_output
from passthrough73.audio import AudioOwner
from passthrough73.alsa import AlsaPump


class FollowTests(unittest.TestCase):
    def test_vendor_blackout_trace_does_not_recommit_under_jitter(self):
        follow = Follow()
        modes = {(3840, 2160, 60, False), (3840, 2160, 60, True)}
        args = (3840, 2160, 59.99, 'sink', modes)
        self.assertIsNone(follow.observe(*args, 0))
        intent = follow.observe(*args, 2)
        follow.committed(intent)
        for n, hz in enumerate([59.97, 59.98, 59.99, 59.86] * 20):
            self.assertIsNone(follow.observe(3840, 2160, hz, 'sink', modes, n + 3))
        follow.disconnected()
        self.assertIsNone(follow.observe(*args, 100))
        self.assertIsNotNone(follow.observe(*args, 102))

    def test_mapped_pixels_are_never_relabelled_as_hdr(self):
        self.assertEqual(hdr_output(False, 'SDR', 'PQ', True, {'PQ'}), ('SDR', True))
        with self.assertRaises(ValueError):
            hdr_output(True, 'SDR', 'PQ', True, {'PQ'})
        with self.assertRaises(ValueError):
            hdr_output(False, 'PQ', 'PQ', False, {'PQ'})

    def test_pcm_pump_owns_one_rx_and_tx_and_gap_does_not_reopen(self):
        owner = AudioOwner()
        owner.configure_source(1, 48000)
        owner.subscribe('opus')
        pcm = Mock(capture_xruns=0)
        pcm.acquire.side_effect = ['rx', 'tx']
        pcm.read.side_effect = [256, 0, 256]
        pump = AlsaPump(owner, pcm, 'hw:RX', 'hw:TX')
        for _ in range(3):
            pump.step()
        self.assertEqual(pcm.acquire.call_count, 2)
        self.assertEqual(pcm.configure.call_count, 2)
        self.assertEqual(owner.tx_gap_frames, 256)
        self.assertIsNotNone(owner.take('opus'))
        pump.close()
