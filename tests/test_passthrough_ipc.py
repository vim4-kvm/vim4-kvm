import importlib.util
import errno
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('passthrough_' + name,
        ROOT / 'packaging/passthrough73' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ipc, leases, audio = load('ipc'), load('leases'), load('audio')


class IPCTests(unittest.TestCase):
    def setUp(self):
        try:
            self.server, self.client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        except OSError as error:
            if error.errno in (errno.EPROTONOSUPPORT, errno.ESOCKTNOSUPPORT):
                self.skipTest('AF_UNIX SOCK_SEQPACKET unavailable; run on Linux')
            raise
        self.addCleanup(self.server.close)
        self.addCleanup(self.client.close)

    def test_rights_are_real_owned_descriptors(self):
        with tempfile.TemporaryFile() as file:
            file.write(b'complete frame')
            file.flush()
            ipc.send_packet(self.server, {'type': 'frame'}, [file.fileno()])
            message, fds = ipc.receive_packet(self.client)
        self.assertEqual(message['version'], 1)
        self.assertEqual(len(fds), 1)
        try:
            self.assertEqual(os.pread(fds[0], 14, 0), b'complete frame')
            self.assertFalse(os.get_inheritable(fds[0]))
        finally:
            os.close(fds[0])

    def make_peer(self, fd):
        broker = leases.FrameBroker()
        broker.begin_generation(1, [leases.Buffer(i, fd, 4096) for i in range(8)])
        ipc.send_packet(self.client, {'op': 'subscribe', 'name': 'onekvm', 'in_flight_limit': 2})
        peer = ipc.BrokerPeer.accept(self.server, broker)
        ipc.receive_packet(self.client)
        frame = leases.Frame(1, 0, 3, 123, 32, 16, 32, 512, 'rec709', 'limited')
        broker.publish(frame)
        ipc.send_packet(self.client, {'op': 'take'})
        peer.handle()
        packet, fds = ipc.receive_packet(self.client)
        for received in fds:
            os.close(received)
        return broker, peer, packet

    def test_ack_and_disconnect_are_not_dma_retirement(self):
        with tempfile.TemporaryFile() as file:
            broker, peer, packet = self.make_peer(file.fileno())
            ipc.send_packet(self.client, {'op': 'release', 'token': packet['token'], 'generation': 1})
            peer.handle()
            self.assertEqual(ipc.receive_packet(self.client)[0]['type'], 'release-pending')
            self.assertEqual(broker.take_recyclable(), [])
            peer.disconnect()
            self.assertEqual(broker.take_recyclable(), [])
            peer.confirm_retired(packet['token'])
            self.assertEqual(broker.take_recyclable(), [(1, 0)])

    def test_old_generation_ack_cannot_retire_frame(self):
        with tempfile.TemporaryFile() as file:
            broker, peer, packet = self.make_peer(file.fileno())
            ipc.send_packet(self.client, {'op': 'release', 'token': packet['token'], 'generation': 0})
            with self.assertRaises(ValueError):
                peer.handle()
            self.assertEqual(broker.take_recyclable(), [])

    def test_client_cannot_send_unexpected_rights(self):
        with tempfile.TemporaryFile() as file:
            ipc.send_packet(self.client, {'op': 'take'}, [file.fileno()])
            with self.assertRaisesRegex(ValueError, 'must not carry'):
                ipc.receive_request(self.server)

    def test_unknown_version_and_truncation_fail(self):
        self.client.send(b'{"version":2}')
        with self.assertRaises(ValueError):
            ipc.receive_packet(self.server)
        self.client.send(b'x' * (ipc.MAX_PACKET + 1))
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            ipc.receive_packet(self.server)


class AudioTests(unittest.TestCase):
    def test_rx_xrun_recovers_same_endpoint_without_resetting_tx_queue(self):
        owner = audio.AudioOwner(period_frames=2)
        owner.configure_source(1, 48000)
        owner.enable_tx(True)
        period = audio.PCMPeriod(1, 0, 48000, b'\x01\x00' * 4)
        owner.feed(period)
        calls = []
        self.assertTrue(owner.recover_capture(-errno.EPIPE,
                        lambda error, silent: calls.append((error, silent)) or 0))
        self.assertEqual(calls, [(-errno.EPIPE, 1)])
        self.assertEqual(owner.take_tx(), period.data)
        self.assertEqual(owner.capture_xruns, 1)
        with self.assertRaises(OSError):
            owner.recover_capture(-errno.ENODEV, lambda *args: self.fail('not recoverable'))

    def test_local_audio_survives_remote_disconnect_and_rx_gap(self):
        owner = audio.AudioOwner(period_frames=2, queue_periods=2)
        owner.configure_source(1, 48000)
        owner.enable_tx(True)
        owner.subscribe('onekvm')
        period = audio.PCMPeriod(1, 0, 48000, b'\x01\x00' * 4)
        owner.feed(period)
        owner.disconnect('onekvm')
        self.assertEqual(owner.take_tx(), period.data)
        self.assertEqual(owner.take_tx(), bytes(8))
        self.assertEqual(owner.tx_gap_frames, 2)
        owner.feed(period)
        self.assertEqual(owner.take_tx(), period.data)

    def test_slow_remote_queue_is_bounded_and_old_generation_rejected(self):
        owner = audio.AudioOwner(period_frames=2, queue_periods=2)
        owner.configure_source(1, 44100)
        owner.subscribe('pikvm')
        for sequence in range(3):
            owner.feed(audio.PCMPeriod(1, sequence, 44100, bytes(8)))
        self.assertEqual(owner.dropped_periods['pikvm'], 1)
        self.assertEqual(owner.take('pikvm').sequence, 1)
        owner.configure_source(2, 48000)
        self.assertIsNone(owner.take('pikvm'))
        with self.assertRaises(ValueError):
            owner.feed(audio.PCMPeriod(1, 4, 44100, bytes(8)))
