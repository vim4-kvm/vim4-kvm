#!/usr/bin/env python3
"""Report kernel encoder quarantine; optionally reboot an unused KVM board."""
import json
import os
from pathlib import Path
import subprocess
import time

DRIVER = Path('/sys/bus/platform/drivers/vdec')
RUNTIME = Path('/run/vim4-wave5')
APPS = ('one-kvm.service', 'nanokvm.service', 'vim4-kvm.service', 'vim4-pikvm.service')
LUNS = Path('/sys/kernel/config/usb_gadget')


def quarantine(driver=DRIVER):
    for path in driver.glob('*/isolated'):
        try:
            if path.read_text().strip() == '1':
                return {'device': path.parent.name, 'isolated': True,
                        'reason': (path.parent / 'isolation_reason').read_text().strip(),
                        'timeBoottimeNs': (path.parent / 'isolation_time_ns').read_text().strip()}
        except OSError:
            continue
    return None


def unused(run=subprocess.run, luns=LUNS):
    # Stream/status.clients omits shared consumers (UU, RTSP, recording, ...).
    # Only inactive applications prove no demand with the current runtime API.
    result = run(['systemctl', 'show', '--property=ActiveState', '--value', *APPS],
                 capture_output=True, text=True, timeout=3, check=False)
    states = [line for line in result.stdout.splitlines() if line]
    if result.returncode or len(states) != len(APPS) or any(s != 'inactive' for s in states):
        return False
    try:
        # A reboot must not interrupt a host's mounted virtual medium.
        return all(not p.read_text().strip() for p in luns.glob('*/functions/mass_storage.*/lun.*/file'))
    except OSError:
        return False


class Monitor:
    def __init__(self, runtime=RUNTIME, auto_reboot=False, idle_seconds=60):
        self.runtime = runtime
        self.auto_reboot = auto_reboot
        self.idle_seconds = max(30, idle_seconds)
        self.reported = False
        self.idle_since = None

    def step(self, alert, now, idle_check=unused, run=subprocess.run):
        if not alert:
            self.idle_since = None
            return
        if not self.reported:
            self.runtime.mkdir(parents=True, exist_ok=True)
            temporary = self.runtime / 'alert.json.tmp'
            temporary.write_text(json.dumps(alert) + '\n')
            temporary.replace(self.runtime / 'alert.json')
            print('Wave5 isolated; reboot required: ' + json.dumps(alert), flush=True)
            self.reported = True
        attempted = self.runtime / 'reboot-attempted'
        if not self.auto_reboot or attempted.exists():
            return
        try:
            idle = idle_check()
        except (OSError, subprocess.SubprocessError):
            idle = False
        if not idle:
            self.idle_since = None
            return
        if self.idle_since is None:
            self.idle_since = now
        if now - self.idle_since < self.idle_seconds:
            return
        # Persist before calling systemd so a service restart cannot retry.
        attempted.touch(exist_ok=False)
        print('Wave5 isolated; applications inactive and media empty; requesting reboot', flush=True)
        run(['systemctl', 'reboot'], check=True, timeout=10)


def main():
    monitor = Monitor(auto_reboot=os.environ.get('WAVE5_AUTO_REBOOT', '0') == '1',
                      idle_seconds=int(os.environ.get('WAVE5_REBOOT_IDLE_SECONDS', '60')))
    while True:
        monitor.step(quarantine(), time.monotonic())
        time.sleep(2)


if __name__ == '__main__':
    main()
