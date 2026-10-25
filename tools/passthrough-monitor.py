#!/usr/bin/env python3
"""Read-only vendor HDMI health window; never modeset or restart services."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


class ScanoutHealth:
    def __init__(self):
        self.frame = None
        self.progress = None
        self.ready_since = None
        self.stalled = False
        self.unready = False
        self.stalls = 0
        self.ready_losses = 0

    def observe(self, now, enabled, signal, ready, frame):
        if not enabled or not signal:
            self.frame = frame
            self.progress = now
            self.ready_since = None
            self.stalled = self.unready = False
            return
        if ready:
            self.ready_since = None
            self.unready = False
        else:
            if self.ready_since is None:
                self.ready_since = now
            if now - self.ready_since >= 2 and not self.unready:
                self.ready_losses += 1
                self.unready = True
        if self.frame != frame or self.progress is None:
            self.frame, self.progress, self.stalled = frame, now, False
        if ready and now - self.progress >= 2 and not self.stalled:
            self.stalls += 1
            self.stalled = True


def read(path):
    return Path(path).read_text().strip()


def run(seconds, output):
    start = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    boot = read('/proc/sys/kernel/random/boot_id')
    deadline = time.monotonic() + seconds
    health = ScanoutHealth()
    captures = [path for path in Path('/sys/class/video4linux').glob('video*')
                if (path / 'name').read_text().strip() == 'vfm_cap']
    if len(captures) != 1:
        raise ValueError('Expected one vfm_cap signal-state endpoint')
    samples = 0
    with output.open('x') as stream:
        while True:
            if read('/proc/sys/kernel/random/boot_id') != boot:
                raise RuntimeError('Board rebooted during observation')
            state = json.loads(read('/run/vim4-passthrough/state.json'))
            values = dict(line.split(':', 1) for line in read(captures[0] / 'status').splitlines() if ':' in line)
            signal = values.get('sm_state', '').strip() == '5'
            ready = read('/sys/class/amhdmitx/amhdmitx0/ready') == '1'
            frame = int(read('/sys/module/aml_media/parameters/display_frame_count'))
            now = time.monotonic()
            health.observe(now, state['state'].get('enabled', False), signal, ready, frame)
            stream.write(json.dumps({'time': now, 'signal': signal, 'ready': ready, 'frame': frame,
                                    'state': state['state']['state'], 'stalls': health.stalls,
                                    'readyLosses': health.ready_losses}) + '\n')
            stream.flush()
            samples += 1
            if now >= deadline:
                break
            time.sleep(min(1, deadline - now))
        journal = subprocess.check_output(['journalctl', '-k', '-b', '--since', start, '--no-pager'], text=True)
        result = {'since': start, 'seconds': seconds, 'samples': samples, 'bootId': boot,
                  'txModesets': journal.count('hdmitx_set_dispmode'),
                  'rxLinkLosses': journal.count('(FSM_SIG_READY) to (FSM_WAIT_CLK_STABLE)'),
                  'scanoutStalls': health.stalls, 'readyLosses': health.ready_losses,
                  'note': 'Software/link evidence only; not an optical black-screen detector'}
        stream.write(json.dumps({'result': result}) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if not 1 <= arguments.seconds <= 86400:
        parser.error('--seconds must be between 1 and 86400')
    run(arguments.seconds, arguments.output)
