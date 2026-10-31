"""Independent experimental capture owner. Run with python3 -m passthrough73.service.

Requires the compiled devices.c library. Device IDs are explicit; this entry
does not change EDID or choose an unverified connector. Manager support remains
false until HDR/readback and automatic source/sink qualification are connected.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import selectors
import select
import socket

from .devices import CaptureDevice, Scanout, _check
from .ipc import BrokerPeer, receive_request, send_packet
from .leases import FrameBroker


def status(preferences, frames):
    return dict(supported=False, **preferences, state='unsupported', output=None,
                reason='Experimental broker: automatic output qualification pending',
                capturedFrames=frames)


def run(args):
    directory = Path(args.runtime)
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory / 'owner.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    capture = CaptureDevice(args.capture, count=args.buffers, library=args.library)
    broker = FrameBroker()
    broker.begin_generation(capture.generation, capture.buffers)
    selector = selectors.DefaultSelector()
    selector.register(capture.fileno(), selectors.EVENT_READ, 'capture')
    peers, fences, displays = [], {}, []
    preferences = dict(enabled=args.display, audio=False, hdr=True)
    frames = 0
    drm = os.open(args.drm, os.O_RDWR | os.O_CLOEXEC) if args.display else None
    display = None
    if drm is not None:
        _check(capture.lib.pt_modeset(drm, args.connector, args.crtc,
                                     capture.width, capture.height), 'atomic modeset')
        display = broker.subscribe('local-display', 3)
    for name in ('capture', 'control'):
        path = directory / (name + '.sock')
        path.unlink(missing_ok=True)  # Only the lock holder owns these endpoints.
        server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        server.bind(str(path))
        os.chmod(path, 0o660)
        server.listen(8)
        server.setblocking(False)
        selector.register(server, selectors.EVENT_READ, name + '-listen')
    capture.start()
    try:
        while True:
            for key, _ in selector.select(0.005):
                kind, client = key.data, key.fileobj
                if kind == 'capture':
                    frame = capture.read_frame()
                    if frame is not None:
                        frames += 1
                        broker.publish(frame)
                elif isinstance(kind, str) and kind.endswith('-listen'):
                    client, _ = client.accept()
                    client.setblocking(False)
                    selector.register(client, selectors.EVENT_READ,
                                      'capture-client' if kind == 'capture-listen' else 'control')
                elif kind == 'control':
                    try:
                        request = receive_request(client)
                        if request['op'] == 'set':
                            raise ValueError('Output qualification pending; preferences unchanged')
                        if request['op'] != 'status':
                            raise ValueError('Unknown control request')
                        send_packet(client, dict(state=status(preferences, frames)))
                    except (ValueError, OSError, EOFError):
                        pass
                    finally:
                        selector.unregister(client)
                        client.close()
                else:
                    try:
                        if kind == 'capture-client':
                            peer = BrokerPeer.accept(client, broker)
                            peers.append(peer)
                            selector.modify(client, selectors.EVENT_READ, peer)
                        else:
                            kind.handle()
                    except (ValueError, OSError, EOFError):
                        selector.unregister(client)
                        if isinstance(kind, BrokerPeer):
                            kind.disconnect()
                        else:
                            client.close()
            if display is not None:
                lease = broker.take(display)
                if lease is not None:
                    scanout = Scanout(drm, broker.buffers[lease.frame.index].dmabuf_fd,
                                      lease.frame, library=args.library)
                    try:
                        scanout.commit(args.plane, args.crtc, test_only=True)
                        scanout.commit(args.plane, args.crtc)
                    except OSError:
                        broker.pin_fault(lease)
                        raise
                    displays.append((scanout, lease))
            for scanout, lease in displays[:]:
                if scanout.retired():
                    scanout.close()
                    broker.retire(lease)
                    displays.remove((scanout, lease))
            for peer in peers:
                # Export the READ snapshot only after the client drops its last
                # software reference. A disconnect alone never enters this path.
                for token in list(peer.release_requested):
                    identity = (peer.consumer, token)
                    if identity not in fences:
                        lease = peer.in_flight[token]
                        fd = broker.buffers[lease.frame.index].dmabuf_fd
                        fences[identity] = _check(capture.lib.pt_reader_fence(fd), 'reader fence')
                    if select.select([fences[identity]], [], [], 0)[0]:
                        os.close(fences.pop(identity))
                        peer.confirm_retired(token)
            for generation, index in broker.take_recyclable():
                capture.requeue(generation, index)
    finally:
        # Never report reader completion merely because the process is stopping.
        # Closing the capture owner cannot reclaim exported peer DMA references.
        broker.stop_generation()
        capture.stop()
        for peer in peers:
            peer.disconnect()
        capture.close()
        selector.close()
        if drm is not None:
            os.close(drm)
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--library')
    parser.add_argument('--runtime', default='/run/vim4-passthrough')
    parser.add_argument('--buffers', type=int, default=14)
    parser.add_argument('--display', action='store_true')
    parser.add_argument('--drm', default='/dev/dri/card0')
    for name in ('connector', 'crtc', 'plane'):
        parser.add_argument('--' + name, type=int)
    args = parser.parse_args()
    if args.display and not all((args.connector, args.crtc, args.plane)):
        parser.error('--display requires explicit connector/crtc/plane IDs')
    run(args)


if __name__ == '__main__':
    main()
