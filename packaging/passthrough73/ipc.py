"""Version 1 local seqpacket protocol; SCM_RIGHTS transfers one DMA-buf per frame.

ACK expresses client intent to release. Only a trusted adapter's proven hardware
retirement may actually recycle a lease. Disconnect does not prove retirement.
"""
import array
from dataclasses import asdict
import fcntl
import json
import os
import socket

VERSION = 1
MAX_PACKET = 16384


def send_packet(sock, message, fds=()):
    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET:
        raise ValueError('Require SOCK_SEQPACKET')
    data = json.dumps(dict(message, version=VERSION), separators=(',', ':')).encode()
    if len(data) > MAX_PACKET:
        raise ValueError('Packet too large')
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', fds))] if fds else []
    if sock.sendmsg([data], ancillary) != len(data):
        raise OSError('Incomplete seqpacket send')


def receive_packet(sock):
    """Return (message, owned_fds); close every received fd on malformed input."""
    fds = []
    try:
        data, controls, flags, _ = sock.recvmsg(MAX_PACKET, socket.CMSG_SPACE(8 * array.array('i').itemsize),
                                              getattr(socket, 'MSG_CMSG_CLOEXEC', 0))
        for level, kind, payload in controls:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                rights = array.array('i')
                rights.frombytes(payload[:len(payload) - len(payload) % rights.itemsize])
                fds.extend(rights)
        # macOS lacks MSG_CMSG_CLOEXEC; make ownership safe on both hosts.
        for fd in fds:
            fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
        if not data:
            raise EOFError('Broker peer disconnected')
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ValueError('Truncated IPC packet')
        message = json.loads(data)
        if not isinstance(message, dict) or message.get('version') != VERSION:
            raise ValueError('Unsupported protocol version')
        return message, fds
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise


def receive_request(sock):
    message, fds = receive_packet(sock)
    if fds:
        for fd in fds:
            os.close(fd)
        raise ValueError('Client requests must not carry file descriptors')
    return message


class BrokerPeer:
    def __init__(self, sock, broker, consumer):
        self.sock, self.broker, self.consumer = sock, broker, consumer
        self.in_flight = {}
        self.release_requested = set()
        self.connected = True

    @classmethod
    def accept(cls, sock, broker):
        message = receive_request(sock)
        name, limit = message.get('name'), message.get('in_flight_limit')
        if message.get('op') != 'subscribe' or not isinstance(name, str) or not name or \
                type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError('Invalid subscribe request')
        consumer = broker.subscribe(name, limit)
        peer = cls(sock, broker, consumer)
        try:
            send_packet(sock, {'type': 'ready', 'consumer': consumer})
        except BaseException:
            peer.disconnect()
            raise
        return peer

    def handle(self):
        message = receive_request(self.sock)
        if message.get('op') == 'take':
            lease = self.broker.take(self.consumer)
            if lease is None:
                send_packet(self.sock, {'type': 'idle'})
                return
            self.in_flight[lease.token] = lease
            buffer = self.broker.buffers[lease.frame.index]
            # Even a failed send retains the lease: disconnect cannot establish
            # whether a consumer handed a descriptor to hardware.
            send_packet(self.sock, {'type': 'frame', 'token': lease.token,
                        'consumer': self.consumer, 'frame': asdict(lease.frame),
                        'format': 'NV12', 'modifier': 0,
                        'allocation_size': buffer.allocation_size}, [buffer.dmabuf_fd])
        elif message.get('op') == 'release':
            token = message.get('token')
            lease = self.in_flight.get(token)
            if lease is None or message.get('generation') != lease.frame.generation:
                raise ValueError('Unknown lease or generation')
            self.release_requested.add(token)
            send_packet(self.sock, {'type': 'release-pending', 'token': token})
        else:
            raise ValueError('Unknown frame request')

    def confirm_retired(self, token):
        """Trusted adapter callback after hardware completion, never raw client ACK."""
        lease = self.in_flight[token]
        self.broker.retire(lease)
        del self.in_flight[token]
        self.release_requested.discard(token)

    def disconnect(self):
        if self.connected:
            self.connected = False
            self.broker.disconnect(self.consumer)
            self.sock.close()
