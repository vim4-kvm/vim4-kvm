"""Linux DRM hotplug notifications; never pulses input HPD or rewrites EDID."""
import socket


class ConnectorEvents:
    def __init__(self):
        self.socket = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM | socket.SOCK_NONBLOCK, 15)
        self.socket.bind((0, 1))  # NETLINK_KOBJECT_UEVENT multicast

    def changed(self):
        changed = False
        while True:
            try:
                data = self.socket.recv(8192)
            except BlockingIOError:
                return changed
            fields = set(data.split(b'\0'))
            changed |= b'SUBSYSTEM=drm' in fields and b'HOTPLUG=1' in fields

    def close(self):
        self.socket.close()
