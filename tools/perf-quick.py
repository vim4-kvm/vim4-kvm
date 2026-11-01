#!/usr/bin/env python3
"""Quick video experiment support; dispatch latency includes the source HTTP leg.

MCP and native sampling require a board-queue ticket. The source server uses no HID.
"""
import argparse
import importlib.machinery
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('board_window', str(ROOT / 'tools/board-window'))
spec = importlib.util.spec_from_loader(loader.name, loader)
bw = importlib.util.module_from_spec(spec)
loader.exec_module(bw)

NATIVE_WORK_SECONDS = 30 + 3 * (85 + 20)  # upload, bounded bench and result copies
SERVICE_RECOVERY_SECONDS = 40
RECEIVER_WORK_SECONDS = 111  # startup, bounded receiver, local tunnel teardown
BASELINE_RECOVERY_SECONDS = 240


def require_budget(queue, ticket, seconds):
    item = queue.read(ticket)
    remaining = item['started'] + item['seconds'] - time.time()
    if item['state'] != 'held' or item['heavy'] or remaining < seconds:
        raise RuntimeError(f'board lease cannot cover {seconds}s of work/recovery (remaining {remaining:.1f}s)')


def cleanup(output, actions):
    """Attempt every cleanup, retaining the measurement exception as primary."""
    primary = sys.exception()
    errors = []
    for name, action in actions:
        try:
            action()
        except Exception as error:
            error.add_note(name)
            errors.append(error)
    if errors:
        message = '; '.join(str(error) for error in errors)
        path = output / 'cleanup-errors.json'
        records = json.loads(path.read_text()) if path.exists() else []
        path.write_text(json.dumps(records + [
            dict(error=str(error), step=error.__notes__[-1]) for error in errors]))
        if primary is not None:
            primary.add_note('Cleanup errors: ' + message)
        else:
            raise ExceptionGroup('Cleanup failed', errors)


def restore_owned(queue, ticket, seconds, output, what, action):
    # An expired lease can already belong to the next sampler. Keep an explicit
    # handoff record instead of issuing an unowned service restart/reboot.
    try:
        require_budget(queue, ticket, seconds)
        action()
    except Exception as error:
        (output / 'recovery-required.json').write_text(json.dumps(dict(
            recovery=what, error=str(error), ticket=ticket)))
        raise


def serve(output, port):
    with output.open('x') as log:
        class Handler(BaseHTTPRequestHandler):
            sequence = 0

            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == '/tick':
                    Handler.sequence += 1
                    stamp = time.time_ns() / 1e6
                    record = dict(id=Handler.sequence & 65535, sourceMs=stamp, drawEndMs=stamp)
                    log.write(json.dumps(record) + '\n')
                    log.flush()
                    body = json.dumps(record).encode()
                    content_type = 'application/json'
                elif self.path == '/':
                    body = (ROOT / 'tools/perf-motion.html').read_bytes()
                    content_type = 'text/html'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        HTTPServer(('0.0.0.0', port), Handler).serve_forever()


def mcp(action, arguments, output, url):
    bw.require_board()
    credentials = json.loads(bw.ssh('vim4', 'sudo -n cat /var/lib/one-kvm/mcp/credentials.json'))
    # Do not print credentials or pass them as process arguments.
    key = credentials.get('token') or credentials.get('api_key') or credentials.get('bearer_token')
    if not key:
        raise ValueError('Unknown credential fields: ' + ','.join(credentials))
    client = bw.MCP(url, key)
    if action == 'screenshot':
        client.screenshot(output)
    elif action == 'list':
        client.initialize()
        output.write_text(json.dumps(client.rpc('tools/list', {})))
    else:
        output.write_text(json.dumps(client.call(action, arguments)))


def native(backend, output, reserve_seconds=0):
    queue, ticket = bw.require_board()
    require_budget(queue, ticket, NATIVE_WORK_SECONDS + SERVICE_RECOVERY_SECONDS + reserve_seconds)
    output.mkdir(exist_ok=False)
    remote = '/var/tmp/p0-2-' + str(time.time_ns())
    bw.ssh('vim4', 'mkdir ' + remote)
    subprocess.run(['scp', str(ROOT / 'build/p0-2/vim4-driver-bench'), 'vim4:' + remote + '/bench'], check=True, timeout=30)
    active = bw.ssh('vim4', 'systemctl is-active one-kvm').strip() == 'active'
    secondary = (backend == 'stock' and bw.ssh(
        'vim4', 'cat /sys/module/aml_media/parameters/vdin0_native_hdr').strip() == 'Y')
    try:
        require_budget(queue, ticket, NATIVE_WORK_SECONDS + SERVICE_RECOVERY_SECONDS + reserve_seconds)
        bw.ssh('vim4', 'sudo -n systemctl stop one-kvm')
        queue.sampling(ticket, True)
        (output / 'sampling.json').write_text(json.dumps(queue.read(ticket)))
        for codec in ('capture', 'h264', 'h265'):
            require_budget(queue, ticket, 85 + 20 + SERVICE_RECOVERY_SECONDS + reserve_seconds)
            env = ('GST_PLUGIN_PATH=/usr/lib/vim4-kvm/gstreamer-1.0 LD_LIBRARY_PATH=/opt/vim4-onekvm/lib'
                   if backend == 'stock' else 'GST_PLUGIN_PATH=/usr/lib/vim4-kvm/mainline-gstreamer-1.0')
            if secondary:
                env = ('GST_PLUGIN_PATH=/opt/vim4-onekvm/lib/gstreamer-1.0:/usr/lib/vim4-kvm/gstreamer-1.0 '
                       'LD_LIBRARY_PATH=/opt/vim4-onekvm/lib VIM4_SECONDARY_HDMI_CAPTURE=1 '
                       'GST_V4L2_PREFER_CONTIGUOUS=1')
            command = (f'env {env} GST_REGISTRY={remote}/registry.bin timeout -k 3 75 {remote}/bench '
                       f'--exclusive --backend={backend} --codec={codec} --warmup=120 --frames=1800 '
                       f'--width=1920 --height=1080 --bitrate=12000000 --gop=60 --timeout=65 '
                       f'--output={remote}/{codec}.json' + (' --secondary' if secondary else ''))
            try:
                text = bw.ssh('vim4', command, timeout=85)
                (output / (codec + '.stdout')).write_text(text)
            finally:
                cleanup(output, [('copy benchmark result', lambda: subprocess.run(
                    ['scp', 'vim4:' + remote + '/' + codec + '.json', str(output)], check=False, timeout=20))])
    finally:
        cleanup(output, [('sampling off', lambda: queue.sampling(ticket, False)),
            ('restore service', lambda: restore_owned(queue, ticket, SERVICE_RECOVERY_SECONDS, output,
                'start previously active one-kvm',
                lambda: bw.ssh('vim4', 'sudo -n systemctl start one-kvm', timeout=40)) if active else None)])


def window(args):
    """One bounded sample, with candidate recovery inside the same lease."""
    queue, ticket = bw.require_board()
    started = time.monotonic()
    output = ROOT / 'logs/p0-2-quick' / args.label
    output.mkdir(exist_ok=False)
    tool = [str(ROOT / 'tools/board-window'), '--window', 'p0-2-quick',
            '--device', '/dev/cu.usbserial-1100']

    def step(name, command, timeout):
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

    candidate_started = False
    try:
        if args.candidate:
            require_budget(queue, ticket, 480 + BASELINE_RECOVERY_SECONDS)
            candidate_started = True
            step('boot', tool + ['boot-candidate', str(args.candidate), '--sha256', args.sha256, '--reuse-staged'], 480)
        step('before', tool + ['collect', '--readonly'], 30)
        if args.candidate and time.monotonic() - started > 200:
            raise RuntimeError('Boot used sampling budget; reserve time for baseline recovery')
        recovery_seconds = BASELINE_RECOVERY_SECONDS if args.candidate else 0
        native(args.backend, output / 'native', reserve_seconds=RECEIVER_WORK_SECONDS + 30 + recovery_seconds)
        require_budget(queue, ticket, RECEIVER_WORK_SECONDS + 30 + recovery_seconds)
        tunnel = subprocess.Popen(['ssh', '-o', 'ExitOnForwardFailure=yes', '-NT', '-L',
                                   '127.0.0.1:18082:127.0.0.1:8081', 'vim4'])
        try:
            time.sleep(1)
            queue.sampling(ticket, True)
            (output / 'sampling-receiver.json').write_text(json.dumps(queue.read(ticket)))
            step('receiver', ['node', str(ROOT / 'tools/latency-receiver.mjs'),
                             'http://127.0.0.1:18082', '30', '--one-kvm', '--local-backend',
                             '--expect-codec=h264', '--marker-y=540'], 100)
        finally:
            cleanup(output, [('sampling off', lambda: queue.sampling(ticket, False)),
                ('terminate tunnel', tunnel.terminate), ('reap tunnel', lambda: tunnel.wait(timeout=10))])
        step('after', tool + ['collect', '--readonly'], 30)
    finally:
        if candidate_started and (ROOT / 'logs/p0-2-quick/baseline-proof.json').exists():
            cleanup(output, [('return baseline', lambda: restore_owned(queue, ticket, BASELINE_RECOVERY_SECONDS,
                output, 'return baseline', lambda: step('return', tool + ['return-baseline'], 240)))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('source')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--port', type=int, default=18090)
    p = commands.add_parser('window')
    p.add_argument('--label', required=True)
    p.add_argument('--backend', choices=('stock', 'edge'), required=True)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--sha256')
    p = commands.add_parser('mcp')
    p.add_argument('action')
    p.add_argument('--url', default='http://192.168.50.210:8080/api/mcp')
    p.add_argument('--arguments', type=json.loads, default={})
    p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('native')
    p.add_argument('--backend', choices=('stock', 'edge'), required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'source':
        serve(args.output, args.port)
    elif args.command == 'mcp':
        mcp(args.action, args.arguments, args.output, args.url)
    elif args.command == 'native':
        native(args.backend, args.output)
    else:
        window(args)


if __name__ == '__main__':
    main()
