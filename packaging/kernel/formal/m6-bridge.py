"""Serve only this deployment's fixed M6 assets and collect native results."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import threading
import time

RECEIVER_IP = os.environ.get('VIM4_RECEIVER_IP', '192.168.50.239')
ROOT = Path(__file__).resolve().parent
LOGS = Path(os.environ['VIM4_FINAL_LOGS'])
jobs, results = queue.Queue(), {}
condition = threading.Condition()
assets = {name: Path(os.environ['VIM4_FORMAL_ASSETS']) / 'm6' / name for name in ('client.py', 'host.py', 'input-target', 'hdmi-source-mode', 'latency-source', 'input-source')}


class Handler(BaseHTTPRequestHandler):
    def send(self, value, code=200):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        name = self.path.lstrip('/')
        if name == 'b':
            lines = ['set -eu', 'mkdir -p /tmp/deploy73', 'cd /tmp/deploy73']
            for key, path in assets.items():
                lines += [f'curl -fsS http://{RECEIVER_IP}:18274/{key} -o {key}',
                          f'echo "{hashlib.sha256(path.read_bytes()).hexdigest()}  {key}" | shasum -a 256 -c -']
            lines += ['chmod +x input-target hdmi-source-mode latency-source input-source',
                      f'exec env VIM4_M6_SERVER=http://{RECEIVER_IP}:18274 python3 client.py']
            return self.send(('\n'.join(lines) + '\n').encode())
        if name in assets:
            return self.send(assets[name].read_bytes())
        if name == 'next':
            try:
                return self.send(jobs.get_nowait())
            except queue.Empty:
                return self.send(None)
        self.send_error(404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/result':
            (LOGS / ('m6-job-' + str(data['id']) + '.json')).write_text(json.dumps(data, indent=2) + '\n')
            with condition:
                results[data['id']] = data
                condition.notify_all()
            return self.send(dict(received=True))
        if self.path == '/command' and self.client_address[0] == RECEIVER_IP:
            identifier = time.time_ns()
            jobs.put(dict(data, id=identifier))
            with condition:
                if not condition.wait_for(lambda: identifier in results, timeout=35):
                    return self.send(dict(ok=False, error='M6 did not return a native result'), 504)
                return self.send(results.pop(identifier))
        self.send_error(403)


ThreadingHTTPServer((RECEIVER_IP, 18274), Handler).serve_forever()

