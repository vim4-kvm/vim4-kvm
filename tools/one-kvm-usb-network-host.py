#!/usr/bin/env python3
"""macOS USB network data check; enable one USB NIC in One-KVM beforehand.

Requires exclusive access. Does not change USB configuration or host networking.
Uses SSH for board discovery, then binds curl transfers to the actual USB NIC.
The temporary board listener serves only a deterministic test payload, expires
after 100 seconds, and is terminated by its own reported PID on exit.
"""
import argparse
import hashlib
import ipaddress
import json
import re
import select
import shlex
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--board', default='vim4')
    args = parser.parse_args()

    def remote(*words):
        return subprocess.check_output(['ssh', args.board, shlex.join(words)], timeout=20)

    code = '''import json, subprocess
from pathlib import Path
g=Path('/sys/kernel/config/usb_gadget/kvm')
active=[mode for mode in ('ncm','ecm','rndis') if (g/'configs/c.1'/f'{mode}.usb0').is_symlink()]
assert len(active)==1, 'Enable exactly one USB network function first'
f=g/'functions'/f'{active[0]}.usb0'
n=(f/'ifname').read_text().strip()
d=json.loads(subprocess.check_output(['ip','-j','address','show','dev',n]))[0]
a=next(a for a in d['addr_info'] if a['family']=='inet')
print(json.dumps(dict(mode=active[0],interface=n,ip=a['local'],prefixlen=a['prefixlen'])))
'''
    state = json.loads(remote('python3', '-c', code))
    network = ipaddress.ip_network(f"{state['ip']}/{state['prefixlen']}", strict=False)
    end = time.monotonic() + 60
    host_interface = None
    while time.monotonic() < end:
        text = subprocess.check_output(['ifconfig', '-a'], text=True)
        for block in re.split(r'\n(?=\S)', text):
            addresses = re.findall(r'\binet (\d+\.\d+\.\d+\.\d+)', block)
            if ('status: active' in block and block.startswith('en') and
                    any(ipaddress.ip_address(address) in network for address in addresses)):
                host_interface = block.split(':')[0]
                break
        if host_interface:
            break
        time.sleep(.25)
    if not host_interface:
        raise RuntimeError('No active USB host interface in the gadget subnet; inspect DHCP')

    # Record the lease, rather than treating enumeration as data acceptance.
    packet = subprocess.check_output(['ipconfig', 'getpacket', host_interface], text=True)
    assert 'dhcp_message_type (uint8): ACK' in packet, packet
    assert f"server_identifier (ip): {state['ip']}" in packet, packet
    server_code = '''import hashlib,json,time,os
from http.server import HTTPServer,BaseHTTPRequestHandler
payload=bytes(range(256))*4096
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_POST(self):
  size=int(self.headers.get('Content-Length','0'))
  if size!=len(payload):self.send_error(400);return
  data=self.rfile.read(size);body=json.dumps(dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())).encode()
  self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=HTTPServer((ADDRESS,17741),Handler);server.timeout=1
deadline=time.monotonic()+100
print(json.dumps(dict(pid=os.getpid())),flush=True)
while time.monotonic()<deadline:server.handle_request()
server.server_close()
'''.replace('ADDRESS', repr(state['ip']))
    server = subprocess.Popen(['ssh', args.board, 'python3', '-u', '-'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    remote_pid = None
    try:
        server.stdin.write(server_code.encode())
        server.stdin.close()
        if not select.select([server.stdout], [], [], 10)[0]:
            raise TimeoutError('USB listener did not become ready')
        remote_pid = json.loads(server.stdout.readline())['pid']
        assert isinstance(remote_pid, int) and remote_pid > 1
        target = f"http://{state['ip']}:17741/"
        curl = ['curl', '--fail', '--silent', '--show-error', '--interface', host_interface,
                '--connect-timeout', '3', '--max-time', '10']
        expected = bytes(range(256)) * 4096
        received = subprocess.check_output([*curl, target], timeout=15)
        digest = hashlib.sha256(expected).hexdigest()
        assert hashlib.sha256(received).hexdigest() == digest
        accepted = json.loads(subprocess.check_output(
            [*curl, '--data-binary', '@-', target], input=expected, timeout=15))
        assert accepted['bytes'] == len(expected) and accepted['sha256'] == digest
        print(json.dumps(dict(mode=state['mode'], board_interface=state['interface'],
                              host_interface=host_interface, usb_address=state['ip'],
                              dhcp_ack=True, downloaded_bytes=len(received),
                              uploaded_bytes=accepted['bytes'], sha256=digest)))
    finally:
        if remote_pid and server.poll() is None:
            subprocess.run(['ssh', args.board, 'kill', '-TERM', str(remote_pid)],
                           check=False, timeout=10, stdout=subprocess.DEVNULL)
        if server.poll() is None:
            server.terminate()
        server.wait(timeout=10)


if __name__ == '__main__':
    main()
