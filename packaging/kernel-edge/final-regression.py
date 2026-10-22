#!/usr/bin/env python3
"""Snapshot the qualified board-window fixtures offline, then run them serially.

prepare never uses SSH or locks. run is only for final-window.py's locked child.
Snapshots live in build/, with a digest receipt; original session files and logs
are never edited. Wi-Fi scanning requires explicit --wifi-scan at preparation;
P2P is never operated.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REMOTE = '/var/tmp/vim4-deploy-7.3-final'
IDS = ('hdmi-modes', 'h264', 'h265', '4k60', 'audio', 'hid', 'media', 'gpu', 'manager')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(args):
    destination = args.destination.resolve()
    destination.mkdir()
    video, audio = destination / 'video', destination / 'audio'
    video.mkdir()
    audio.mkdir()
    (destination / 'gpu-ir-deploy').mkdir()
    logs = args.logs.resolve()
    samples = list(map(int, args.sample_modes.split(','))) if args.sample_modes else list(range(19))
    assert samples and len(set(samples)) == len(samples) and set(samples) <= set(range(19))
    replacements = {
        'logs/kernel-edge/final': str(logs / 'video'),
        'logs/kernel-edge/hdmi-audio': str(logs / 'audio'),
        'build/kernel-edge/final': str(video),
        'build/kernel-edge/hdmi-audio': str(audio),
        '/var/tmp/vim4-7.3-final': REMOTE,
        '../../../tools/manager-login.mjs': (ROOT / 'tools/manager-login.mjs').as_uri(),
        "HERE.parent/'mac-hdr-mode'": repr(str(ROOT / 'build/kernel-edge/mac-hdr-mode')),
    }

    def copy(source, target):
        shutil.copy2(source, target)
        if target.suffix in ('.py', '.mjs'):
            text = target.read_text()
            for old, new in replacements.items():
                text = text.replace(old, new)
            if target.name == 'raw-modes.py':
                marker = "        emit({'switch':mode,"
                assert text.count(marker) == 1, 'Unexpected raw mode fixture layout'
                text = text.replace(marker, "        if mode['id'] not in " + repr(samples) + ": continue\n" + marker)
            target.write_text(text)

    for name in ('fixture.py', 'modes.jsonl', 'configure', 'watch-source-events', 'display-list',
                 'raw-modes.py', 'browser-modes.mjs', 'run-browser.py', 'run-tool.py', 'smoke-4k.py', 'gpu-check.py'):
        copy(args.video_assets / name, video / name)
    copy(ROOT / 'build/kernel-edge/gpu-ir-deploy/latency-source', destination / 'gpu-ir-deploy/latency-source')
    for name in ('browser-rates.py', 'browser-audio.mjs', 'run-browser.py', 'tone', 'mac-audio'):
        copy(args.audio_assets / name, audio / name)
    copy(ROOT / 'build/kernel-edge/usb-edge-transfer.img', destination / 'usb-edge-transfer.img')
    receipt = dict(logs=str(logs), sample_modes=samples, sha256={str(p.relative_to(destination)): sha(p)
                                         for p in destination.rglob('*') if p.is_file()})
    (destination / 'fixtures.json').write_text(json.dumps(receipt, indent=2) + '\n')
    plan = [dict(id=identifier, timeout=900, argv=[sys.executable, str(Path(__file__).resolve()), 'run',
                                                '--destination', str(destination), '--id', identifier])
            for identifier in (*IDS, *(['wifi'] if args.wifi_scan else []))]
    (destination / 'regression.json').write_text(json.dumps(plan, indent=2) + '\n')
    print('PREPARED_OFFLINE', destination / 'regression.json')


def run(args):
    destination = args.destination.resolve()
    receipt = json.loads((destination / 'fixtures.json').read_text())
    for name, expected in receipt['sha256'].items():
        assert sha(destination / name) == expected, name
    logs = Path(receipt['logs'])
    for folder in (logs / 'video', logs / 'audio'):
        folder.mkdir(parents=True, exist_ok=True)
    video, audio = destination / 'video', destination / 'audio'
    env = dict(os.environ)
    env['VIM4_FINAL_LOGS'] = str(logs)
    env.setdefault('PLAYWRIGHT_MODULE', str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'))
    env.setdefault('VIM4_TEST_CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if 'MANAGER_PASSWORD' not in env:
        row = next(line for line in (ROOT / 'docs/hardware.md').read_text().splitlines() if line.startswith('| admin |'))
        env['MANAGER_PASSWORD'] = row.split('|')[2].strip()

    def execute(*argv, **options):
        return subprocess.run(list(map(str, argv)), check=True, cwd=ROOT, env=env, **options)

    identifier = args.id
    if identifier == 'hdmi-modes':
        execute('scp', *[video / name for name in ('fixture.py', 'modes.jsonl', 'configure', 'watch-source-events')], 'vim4:' + REMOTE + '/')
        execute(ROOT / 'build/kernel-edge/mac-hdr-mode', '2', 'off')
        raw = logs / 'video/raw-modes.jsonl'
        with raw.open('w') as output:
            execute(sys.executable, '-u', video / 'raw-modes.py', '--raw-only', stdout=output)
        records = [json.loads(line) for line in raw.read_text().splitlines()]
        passed = {item['mode'] for item in records if item.get('result') == 'passed'}
        assert passed == set(receipt.get('sample_modes', range(19))), ('Requested modes not pattern-qualified', passed)
    elif identifier in ('h264', 'h265'):
        modes = '0,1,5,7,8,10,14,17,18' if identifier == 'h264' else '0,1,5,11,14,16,17,18'
        execute(sys.executable, '-u', video / 'run-browser.py', identifier, modes)
    elif identifier == '4k60':
        execute(sys.executable, '-u', video / 'smoke-4k.py')
    elif identifier == 'audio':
        env.update(AUDIO_RATES='48000,44100,48000', AUDIO_SECONDS='15', AUDIO_COLLECT_ALL='1')
        execute(sys.executable, '-u', audio / 'browser-rates.py')
    elif identifier in ('hid', 'media'):
        tool = 'one-kvm-usb-check.mjs' if identifier == 'hid' else 'one-kvm-usb-media-check.mjs'
        extra = ['--hid-only'] if identifier == 'hid' else ['--service=one-kvm', '--image=' + str(destination / 'usb-edge-transfer.img')]
        execute(sys.executable, video / 'run-tool.py', 'tools/' + tool, '--exclusive', *extra)
    elif identifier == 'gpu':
        execute(sys.executable, video / 'gpu-check.py')
    elif identifier == 'manager':
        execute('node', Path(__file__).with_name('final-manager-check.mjs'))
    elif identifier == 'wifi':
        # Keep saved networks from autoconnecting during this scan. Restore the
        # original radio and per-device autoconnect state even if scanning fails.
        program = '''import subprocess,time
def call(*args):
 return subprocess.check_output(args,text=True,timeout=30).strip()
radio=call('nmcli','radio','wifi')
auto=call('nmcli','-g','GENERAL.AUTOCONNECT','device','show','wlan0')
print('BEFORE radio='+radio+' autoconnect='+auto,flush=True)
try:
 call('nmcli','device','set','wlan0','autoconnect','no')
 call('nmcli','radio','wifi','on')
 deadline=time.monotonic()+20
 while call('nmcli','-g','GENERAL.STATE','device','show','wlan0').startswith('20 '):
  assert time.monotonic()<deadline,'Wi-Fi remained unavailable'
  time.sleep(.5)
 call('nmcli','device','wifi','rescan','ifname','wlan0')
 time.sleep(4)
 results=call('nmcli','-t','-f','SSID,CHAN,SIGNAL,SECURITY','device','wifi','list','ifname','wlan0','--rescan','no')
 print(results,flush=True)
 assert results,'No access points returned'
finally:
 if radio=='disabled':call('nmcli','radio','wifi','off')
 call('nmcli','device','set','wlan0','autoconnect',auto)
 print('AFTER radio='+call('nmcli','radio','wifi')+' autoconnect='+call('nmcli','-g','GENERAL.AUTOCONNECT','device','show','wlan0'),flush=True)
'''
        execute('ssh', 'vim4', 'sudo python3 -', input=program, text=True, timeout=100)
    print('CHECK_PASSED', identifier, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--video-assets', type=Path, default=ROOT / 'build/kernel-edge/final')
    prep.add_argument('--audio-assets', type=Path, default=ROOT / 'build/kernel-edge/hdmi-audio')
    prep.add_argument('--logs', type=Path, required=True)
    prep.add_argument('--destination', type=Path, required=True)
    prep.add_argument('--sample-modes', help='Comma-separated IDs; default checks all 19 modes')
    prep.add_argument('--wifi-scan', action='store_true', help='Explicitly authorize a scan with radio/autoconnect restoration')
    check = commands.add_parser('run')
    check.add_argument('--destination', type=Path, required=True)
    check.add_argument('--id', choices=(*IDS, 'wifi'), required=True)
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else run)(args)


if __name__ == '__main__':
    main()
