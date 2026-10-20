#!/usr/bin/env python3
"""macOS CRG trial: real HID input plus read-only USB storage across rebinds.

Compile tools/input-target.swift first. Copy crg-udc-check.py to the board's /tmp.
Requires exclusive access, an already booted CRG trial kernel, and a dedicated FAT
image containing marker.txt and payload.bin. Never use a real user's disk image.
"""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
from pathlib import Path
import plistlib
import queue
import shlex
import subprocess
import threading
import time


def run(arguments):
    return subprocess.check_output(arguments, text=True).strip()


def host_state():
    return json.loads(run(['osascript', '-l', 'JavaScript', '-e', '''
ObjC.import("AppKit");
const p=$.NSEvent.mouseLocation, f=$.NSScreen.screens.objectAtIndex(0).frame;
JSON.stringify({x:p.x/f.size.width,y:1-p.y/f.size.height,
flags:Number($.NSEvent.modifierFlags),screens:Number($.NSScreen.screens.count),
front:Number($.NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier)})
''']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true', required=True)
    parser.add_argument('--board', default='vim4')
    parser.add_argument('--image', required=True)
    parser.add_argument('--payload-sha256', required=True)
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--target', type=Path, default=Path('/tmp/vim4-input-target'))
    parser.add_argument('--volume', type=Path, default=Path('/Volumes/CRG7319'))
    args = parser.parse_args()
    if not 1 <= args.cycles <= 20 or not args.target.is_file():
        parser.error('Requires 1..20 cycles and a compiled input-target executable')
    initial = host_state()
    if initial['screens'] != 1 or initial['flags']:
        parser.error('Requires one display and all keyboard modifiers released')

    def remote(command):
        return run(['ssh', '-o', 'BatchMode=yes', args.board, shlex.join(command)])

    def report(number, data):
        # Each invocation closes its fd; the board trial separately retains an old
        # relative HID fd/epoll across rebinds to exercise that lifecycle too.
        code = f'''import os, time
fd = os.open('/dev/hidg{number}', os.O_WRONLY | os.O_NONBLOCK)
try:
    deadline = time.monotonic() + 3
    while True:
        try:
            written = os.write(fd, bytes.fromhex('{data.hex()}'))
            if written != {len(data)}:
                raise OSError(f'Short HID write: {{written}}')
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError('HID request did not complete')
            time.sleep(.01)
finally:
    os.close(fd)
'''
        remote(['sudo', '-n', 'python3', '-c', code])

    board_lines = queue.Queue()
    target_lines = queue.Queue()

    def collect(stream, destination, label):
        for line in stream:
            print(f'{label}: {line.rstrip()}', flush=True)
            destination.put(line)
        destination.put(None)

    target = None
    board = None
    mounted = False
    try:
        board_command = ['sudo', '-n', 'python3', '-u', '/tmp/crg-udc-check.py',
                         '--exclusive', '--cycles', str(args.cycles), '--keep-fd',
                         '--storage-image', args.image]
        board = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', args.board,
                                  shlex.join(board_command)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        threading.Thread(target=collect, args=(board.stdout, board_lines, 'board'), daemon=True).start()
        for cycle in range(args.cycles):
            deadline = time.monotonic() + 45
            while True:
                line = board_lines.get(timeout=max(.01, deadline-time.monotonic()))
                if line is None:
                    raise RuntimeError('Board trial exited before host checks')
                if f'cycle={cycle} host-ready;' in line:
                    break
            deadline = time.monotonic() + 20
            while not (args.volume / 'marker.txt').is_file():
                if time.monotonic() >= deadline:
                    raise TimeoutError('Test USB volume did not mount')
                time.sleep(.2)
            mounted = True
            info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(args.volume)]))
            if info.get('WritableMedia') is not False or info.get('BusProtocol') != 'USB':
                raise RuntimeError('Expected a read-only USB test volume')
            assert (args.volume / 'marker.txt').read_text() == 'VIM4 CRG 7.3 composite storage validation\n'
            print(f'cycle={cycle} storage={info["DeviceIdentifier"]} read-only USB', flush=True)

            target = subprocess.Popen([str(args.target), '100'], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, text=True, bufsize=1)
            target_lines = queue.Queue()
            threading.Thread(target=collect, args=(target.stdout, target_lines, 'target'), daemon=True).start()
            while True:
                line = target_lines.get(timeout=10)
                if line is None:
                    raise RuntimeError('Input target exited')
                if json.loads(line).get('kind') == 'ready':
                    break
            if host_state()['front'] != target.pid:
                raise RuntimeError('Test window did not become the foreground application')

            def verify_payload():
                # Overlap bulk storage traffic with interrupt HID transfers.
                for _ in range(4):
                    with (args.volume / 'payload.bin').open('rb') as source:
                        fcntl.fcntl(source.fileno(), fcntl.F_NOCACHE, 1)
                        digest = hashlib.file_digest(source, 'sha256').hexdigest()
                    if digest != args.payload_sha256:
                        raise RuntimeError(f'USB payload hash mismatch: {digest}')
                return digest

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                payload = pool.submit(verify_payload)
                try:
                    report(0, bytes([2, 0, 0, 0, 0, 0, 0, 0]))
                    assert host_state()['flags'] & (1 << 17), 'Host did not receive Shift press'
                finally:
                    report(0, bytes(8))
                assert not host_state()['flags'] & (1 << 17), 'Shift did not release'
                if host_state()['front'] != target.pid:
                    raise RuntimeError('Test target lost focus before arrow key check')
                try:
                    report(0, bytes([0, 0, 0x4f, 0, 0, 0, 0, 0]))
                finally:
                    report(0, bytes(8))
                keys = set()
                deadline = time.monotonic() + 5
                while len(keys) != 2:
                    event = json.loads(target_lines.get(timeout=max(.01, deadline-time.monotonic())))
                    if event.get('key') == 124 and event['kind'] in ('keydown', 'keyup'):
                        keys.add(event['kind'])
                for x, y in [(.25, .25), (.7, .6)]:
                    data = bytes([0]) + round(x*32767).to_bytes(2, 'little') + round(y*32767).to_bytes(2, 'little') + bytes([0])
                    report(1, data)
                    actual = host_state()
                    assert abs(actual['x']-x) < .02 and abs(actual['y']-y) < .02, actual
                before = host_state()
                report(2, bytes([0, 24, 16, 0]))
                after = host_state()
                assert after['x'] > before['x'] and after['y'] > before['y'], (before, after)
                report(2, bytes(4))
                print(f'cycle={cycle} keyboard/absolute/relative PASS; payload={payload.result()}', flush=True)
            target.stdin.close()
            target.wait(timeout=5)
            target = None
            # SCSI eject, rather than filesystem unmount alone, releases the LUN.
            run(['diskutil', 'eject', info['ParentWholeDisk']])
            mounted = False
            board.stdin.write('continue\n')
            board.stdin.flush()
        board.stdin.close()
        if board.wait(timeout=15):
            raise RuntimeError('Board trial failed during cleanup')
        print(f'PASS: {args.cycles} composite cycles, real keyboard/mice and USB file hashes', flush=True)
    finally:
        if target is not None:
            try:
                report(0, bytes(8))
            finally:
                target.stdin.close()
                target.wait(timeout=5)
        if mounted:
            subprocess.run(['diskutil', 'eject', str(args.volume)], check=False)
        if board is not None and board.poll() is None:
            if not board.stdin.closed:
                board.stdin.close()
            board.wait(timeout=15)


if __name__ == '__main__':
    main()
