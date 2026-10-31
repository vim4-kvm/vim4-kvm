"""Independent experimental capture owner. Run with python3 -m passthrough73.service.

Requires the compiled devices.c library. Device IDs are explicit; this entry
does not change EDID or choose an unverified connector. Manager support remains
false until hardware qualification is reviewed, even when readback is available.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import selectors
import select
import socket
import time

from .devices import CaptureDevice, Scanout, _check
from .ipc import BrokerPeer, receive_request, send_packet
from .leases import FrameBroker
from .events import ConnectorEvents
from .follow import Follow
from .readback import mapped_sdr


def status(preferences, frames, rate=0):
    return dict(supported=False, **preferences, state='unsupported', output=None,
                reason='Experimental broker: hardware qualification pending',
                capturedFrames=frames, inputRate=rate)


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
    changing = False
    output_ready = False
    retry_output_at = 0
    follow = Follow()
    sink_generation = 0
    next_observation = 0
    drm = os.open(args.drm, os.O_RDWR | os.O_CLOEXEC) if args.display else None
    display = None
    connector_events = ConnectorEvents() if drm is not None else None
    sink_signature = capture.lib.pt_connector_signature(drm,args.connector) if drm is not None else None
    if drm is not None:
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
            if not changing and capture.source_changed():
                broker.stop_generation()
                capture.stop()
                selector.unregister(capture.fileno())
                changing = True
                output_ready = False
                follow.disconnected()
                if drm is not None:
                    _check(capture.lib.pt_plane_disable(drm, args.plane), 'disable old generation')
            if connector_events is not None and connector_events.changed():
                observed = capture.lib.pt_connector_signature(drm,args.connector)
                if observed != sink_signature:
                    sink_signature = observed
                    output_ready = False
                    follow.disconnected()
                    sink_generation += 1
                    retry_output_at = time.monotonic() + 2
                    _check(capture.lib.pt_plane_disable(drm, args.plane), 'connector change blank')
            now = time.monotonic()
            if display is not None and not changing and now >= max(next_observation, retry_output_at):
                next_observation = now + .5
                measured = capture.lib.pt_capture_rate(capture.pointer)
                if measured > 0:
                    capture.rate = measured
                    modes = set()
                    for n in (24,25,30,50,60):
                        for fractional in ((False,True) if n in (24,30,60) else (False,)):
                            rate = int(n * 1000 / (1.001 if fractional else 1))
                            if capture.lib.pt_mode_supported(drm,args.connector,capture.width,capture.height,rate) == 1:
                                modes.add((capture.width,capture.height,n,fractional))
                    try:
                        intent = follow.observe(capture.width,capture.height,measured/100,
                                                sink_generation,modes,now)
                    except ValueError:
                        intent = None
                    if intent is not None:
                        rate = int(intent[2] * 1000 / (1.001 if intent[3] else 1))
                        result = capture.lib.pt_modeset_rate(drm,args.connector,args.crtc,
                                                            capture.width,capture.height,rate)
                        output_ready = result == 0
                        if output_ready:
                            follow.committed(intent)
                        else:
                            # Retry only after a new source/connector event.
                            retry_output_at = float('inf')
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
                        state = status(preferences, frames, capture.rate)
                        if output_ready and displays and args.rx_status and args.hdr_status:
                            try:
                                mapped = mapped_sdr(args.rx_status,args.hdr_status,
                                                    capture.colorspace,capture.quantization)
                                state['output'] = dict(hdrToSdr=mapped, pixelEotf='SDR')
                            except (OSError, ValueError, KeyError):
                                state['output'] = None
                        send_packet(client, dict(state=state))
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
            if display is not None and output_ready and not changing:
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
                if not changing:
                    capture.requeue(generation, index)
            if changing and not broker.occupancy()['retained_buffers']:
                generation = capture.generation + 1
                capture.close()
                capture = CaptureDevice(args.capture, generation=generation,
                                        count=args.buffers, library=args.library)
                broker.begin_generation(generation, capture.buffers)
                selector.register(capture.fileno(), selectors.EVENT_READ, 'capture')
                capture.start()
                changing = False
                retry_output_at = time.monotonic() + 2
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
            connector_events.close()
            os.close(drm)
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--library')
    parser.add_argument('--runtime', default='/run/vim4-passthrough')
    parser.add_argument('--buffers', type=int, default=14)
    parser.add_argument('--display', action='store_true')
    parser.add_argument('--rx-status', help='Reviewed RX status path, optional')
    parser.add_argument('--hdr-status', help='Reviewed VDIN hdr_status path, optional')
    parser.add_argument('--drm', default='/dev/dri/card0')
    for name in ('connector', 'crtc', 'plane'):
        parser.add_argument('--' + name, type=int)
    args = parser.parse_args()
    if args.display and not all((args.connector, args.crtc, args.plane)):
        parser.error('--display requires explicit connector/crtc/plane IDs')
    run(args)


if __name__ == '__main__':
    main()
