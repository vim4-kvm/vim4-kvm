#!/usr/bin/env python3
"""Exclusive VIM4 P2P smoke: saved SAE STA + discovery + GO lifecycle.

Run as root on the 7.x board with --exclusive and a working wired connection.
Temporarily gives wlan0 to a private supplicant, then restores NetworkManager.
Does not alter saved profiles. Temporary credentials/logs stay root-private in
/run and are removed on exit. A second physical peer is still required to
qualify negotiation, client association, DHCP and P2P data transfer.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=60).stdout.removesuffix('\n')


def wait_for(predicate, description, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.5)
    raise RuntimeError('Timed out waiting for ' + description)


def quote(value):
    if '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('Unsupported control character in saved Wi-Fi value')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def check(cycles):
    if os.geteuid() or not os.uname().release.startswith('7.'):
        raise RuntimeError('Requires root on the 7.x VIM4')
    if Path('/sys/class/net/eth0/carrier').read_text().strip() != '1':
        raise RuntimeError('Wired recovery connection is required')
    lock = open('/run/lock/vim4-wifi-p2p.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    uuid = run('nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan0')
    if not uuid or uuid == '--':
        raise RuntimeError('Connect the saved SAE client before testing')

    def setting(name):
        return run('nmcli', '--show-secrets', '--escape', 'no', '-g', name, 'connection', 'show',
                   'uuid', uuid)

    if setting('802-11-wireless-security.key-mgmt') != 'sae':
        raise RuntimeError('This test requires an already verified SAE profile')
    ssid = setting('802-11-wireless.ssid')
    password = setting('802-11-wireless-security.psk')
    if not password:
        raise RuntimeError('Saved SAE password is unavailable')
    address = json.loads(run('ip', '-j', '-4', 'address', 'show', 'dev', 'wlan0'))
    address = next(item for item in address[0]['addr_info'] if item['scope'] == 'global')
    gateway = run('nmcli', '-g', 'IP4.GATEWAY', 'device', 'show', 'wlan0')
    if not gateway:
        raise RuntimeError('Saved wireless connection has no IPv4 gateway')
    report = {'cycles': [], 'peer_transfer_verified': False}
    process = None
    owned_groups = set()
    with tempfile.TemporaryDirectory(prefix='vim4-p2p-', dir='/run') as directory:
        directory = Path(directory)
        control = directory / 'ctrl'
        log = directory / 'supplicant.log'
        config = directory / 'wpa.conf'
        config.write_text(
            f'ctrl_interface={control}\nupdate_config=0\n'
            'device_name=VIM4-P2P-test\nconfig_methods=virtual_push_button\n'
            'sae_pwe=2\nnetwork={\n'
            f' ssid={quote(ssid)}\n key_mgmt=SAE\n ieee80211w=2\n'
            f' sae_password={quote(password)}\n}}\n')
        config.chmod(0o600)
        del password

        def cli(interface, *command):
            return run('wpa_cli', '-p', str(control), '-i', interface, *command)

        def status():
            return dict(line.split('=', 1) for line in cli('wlan0', 'status').splitlines()
                        if '=' in line)

        def ok(interface, *command):
            if cli(interface, *command) != 'OK':
                raise RuntimeError('Supplicant command failed: ' + command[0])

        try:
            run('nmcli', 'device', 'set', 'wlan0', 'managed', 'no')
            wait_for(lambda: 'P2P-device' not in run('iw', 'dev'),
                     'NetworkManager to release P2P')
            process = subprocess.Popen(
                ['wpa_supplicant', '-Dnl80211', '-i', 'wlan0', '-c', str(config),
                 '-f', str(log), '-d'], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            wait_for(lambda: (control / 'p2p-dev-wlan0').exists(), 'private P2P control')
            wait_for(lambda: status().get('wpa_state') == 'COMPLETED', 'SAE authentication')
            # Reuse this board's still-current DHCP lease only during the test.
            # This is a data-path check; it does not claim a fresh DHCP exchange.
            run('ip', 'address', 'replace',
                f"{address['local']}/{address['prefixlen']}", 'dev', 'wlan0')
            run('ip', 'route', 'replace', 'default', 'via', gateway,
                'dev', 'wlan0', 'metric', '601')
            run('ping', '-I', 'wlan0', '-c', '3', '-W', '2', gateway)
            initial = status()
            report['sae'] = {key: initial[key] for key in
                             ('key_mgmt', 'pmf', 'sae_h2e', 'sae_group') if key in initial}
            for cycle in range(cycles):
                ok('p2p-dev-wlan0', 'p2p_find', '3', 'type=social')
                time.sleep(4)
                ok('p2p-dev-wlan0', 'p2p_stop_find')
                ok('p2p-dev-wlan0', 'p2p_listen', '2')
                time.sleep(3)
                ok('p2p-dev-wlan0', 'p2p_stop_find')
                # Same-channel and cross-band GO with a linked 5 GHz STA.
                frequency = 5200 if cycle % 2 == 0 else 2412
                before = set(path.name for path in Path('/sys/class/net').glob('p2p-*'))
                ok('p2p-dev-wlan0', 'p2p_group_add', f'freq={frequency}')
                group = wait_for(lambda: next((path.name for path in
                    Path('/sys/class/net').glob('p2p-*') if path.name not in before), ''),
                    'GO netdev')
                owned_groups.add(group)
                wait_for(lambda: (control / group).exists(), 'GO supplicant control')
                wait_for(lambda: dict(line.split('=', 1) for line in
                    cli(group, 'status').splitlines() if '=' in line).get('wpa_state')
                    == 'COMPLETED', 'GO startup')
                time.sleep(2)
                info = run('iw', 'dev', group, 'info')
                if 'type P2P-GO' not in info or f'({frequency} MHz)' not in info:
                    raise RuntimeError('GO role/channel differs from request: ' + info)
                run('ping', '-I', 'wlan0', '-c', '3', '-W', '2', gateway)
                if status().get('wpa_state') != 'COMPLETED':
                    raise RuntimeError('SAE link lost during concurrent GO')
                ok('p2p-dev-wlan0', 'p2p_group_remove', group)
                wait_for(lambda: not Path('/sys/class/net', group).exists(), 'GO deletion')
                owned_groups.discard(group)
                report['cycles'].append({'frequency': frequency, 'go': True,
                                         'sta_gateway_ping': True, 'deleted': True})
                print(json.dumps({'completed_cycle': cycle + 1,
                                  **report['cycles'][-1]}), flush=True)
            text = log.read_text(errors='replace')
            report['events'] = {event: text.count(event) for event in (
                'P2P-GROUP-STARTED', 'P2P-GROUP-REMOVED', 'P2P-FIND-STOPPED',
                'P2P-DEVICE-FOUND', 'CTRL-EVENT-SCAN-RESULTS')}
        except Exception as error:
            print(json.dumps({'test_failure': type(error).__name__, 'detail': str(error)}), flush=True)
            raise
        finally:
            try:
                if process:
                    try:
                        # Finish group deletion before returning its radio to NM.
                        for group in owned_groups:
                            run('wpa_cli', '-p', str(control), '-i', 'p2p-dev-wlan0',
                                'p2p_group_remove', group, check=False)
                            try:
                                wait_for(lambda: not Path('/sys/class/net', group).exists(),
                                         'owned GO cleanup', 10)
                            except RuntimeError:
                                run('iw', 'dev', group, 'del', check=False)
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
            finally:
                # Restore NM even when group deletion or child cleanup fails.
                run('ip', '-4', 'address', 'flush', 'dev', 'wlan0', check=False)
                run('ip', '-4', 'route', 'flush', 'dev', 'wlan0', check=False)
                run('nmcli', 'device', 'set', 'wlan0', 'managed', 'yes')
                # Autoconnect is asynchronous; do not race another activation.
                wait_for(lambda: run('nmcli', '-g', 'GENERAL.CON-UUID', 'device', 'show', 'wlan0')
                         == uuid and run('nmcli', '-g', 'GENERAL.STATE', 'device', 'show', 'wlan0')
                         .startswith('100'), 'NetworkManager to restore the saved connection', 50)
    print(json.dumps(report), flush=True)


def interrupted(signum, frame):
    raise InterruptedError('Test interrupted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exclusive', action='store_true')
    parser.add_argument('--cycles', type=int, default=4, choices=range(1, 11))
    args = parser.parse_args()
    if not args.exclusive:
        parser.error('--exclusive is required after releasing other Wi-Fi tests')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        check(args.cycles)
    except Exception as error:
        # Child commands never contain credentials; do not emit captured output.
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
