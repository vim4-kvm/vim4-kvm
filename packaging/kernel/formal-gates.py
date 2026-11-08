#!/usr/bin/env python3
"""Limited formal regression gates. Exclusive board ticket required; may change EDID, send HID and attach dedicated media.

Audio checks service/device state only. HDMI checks 1080p60/4K60/no-signal only.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

import argparse
from contextlib import contextmanager
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'packaging/kernel/formal'
REMOTE = '/var/tmp/vim4-formal-deploy'
HOST = 'vim4'
RECEIVER_IP = '192.168.50.239'
loader = importlib.machinery.SourceFileLoader('deploy_gate_bw', str(ROOT / 'tools/board-window'))
spec = importlib.util.spec_from_loader(loader.name, loader)
bw = importlib.util.module_from_spec(spec)
loader.exec_module(bw)
def saved(name, data):
    (LOGS / name).write_text(json.dumps(data, indent=2) + '\n')
    return data


def api(path, method='GET', data=None):
    argv = ['node', str(OUT / 'api.mjs'), path, method]
    if data is not None:
        argv.append(json.dumps(data))
    return json.loads(subprocess.check_output(argv, cwd=ROOT, text=True, timeout=40))


def m6(action, **arguments):
    request = urllib.request.Request('http://'+RECEIVER_IP+':18274/command', data=json.dumps(dict(action=action, **arguments)).encode(), headers={'Content-Type': 'application/json'})
    result = json.load(urllib.request.urlopen(request, timeout=40))
    assert result['ok'], result
    return result['result']


def remote(script):
    bw.require_board()
    return bw.ssh_python(HOST, script)


def upload(source, target):
    bw.require_board()
    subprocess.run(['scp','-q',str(source),HOST+':'+target],check=True,timeout=120)
    expected=hashlib.sha256(source.read_bytes()).hexdigest()
    actual=remote("import hashlib;from pathlib import Path\nprint(hashlib.file_digest(Path("+repr(target)+").open('rb'),'sha256').hexdigest())")
    assert actual.strip()==expected, 'Uploaded gate asset differs: '+str(source)


@contextmanager
def gate_tunnel():
    if os.environ.get('VIM4_FORMAL_TUNNEL'):
        yield
        return
    process = subprocess.Popen(['ssh','-N','-oBatchMode=yes','-oExitOnForwardFailure=yes',
                                '-L','18088:127.0.0.1:8081','-L','18080:127.0.0.1:80',HOST],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        time.sleep(.5)
        assert process.poll() is None, 'Gate SSH tunnel failed'
        yield
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill();process.wait()


def status():
    return json.loads(remote("import sys,json;sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4video;print(json.dumps(vim4video.status()))"))


def locked(width, height):
    deadline = time.monotonic() + 40
    while True:
        current = status()
        if current.get('signal') and (current['width'], current['height']) == (width, height):
            assert abs(current['refreshHz']-60) < .5, current
            return current
        if time.monotonic() >= deadline:
            raise TimeoutError(current)
        time.sleep(.5)


def video(name, seconds, width=3840, height=2160, codec=None):
    bw.ready(HOST, timeout=60)
    value = json.loads(subprocess.check_output(['node', 'tools/board-window-receiver.mjs', 'http://127.0.0.1:18088', str(seconds), '--local-ip='+RECEIVER_IP], text=True, timeout=seconds+90))
    saved(name + '.json', value)
    first, last = value['samples'][0], value['samples'][-1]
    assert all((row.get('frameWidth'), row.get('frameHeight')) == (width, height) for row in value['samples'])
    assert value['fps'] >= 57, value['fps']
    for key in ('framesDropped', 'packetsLost', 'freezeCount'):
        assert last.get(key, 0) == first.get(key, 0), (key, first.get(key), last.get(key))
    if codec:
        assert first['codec'].lower() == 'video/' + codec.lower(), first['codec']
    print(name, value['fps'], last['framesDecoded']-first['framesDecoded'], flush=True)


def credential_mcp():
    c = json.loads(bw.ssh(HOST, 'sudo -n cat /var/lib/one-kvm/mcp/credentials.json'))
    return bw.MCP('http://127.0.0.1:18088/api/mcp', c.get('token') or c.get('api_key') or c.get('bearer_token'))


def hid(label):
    started = m6('hid_start')
    assert '"kind":"ready"' in started['output']
    client = credential_mcp()
    try:
        client.screenshot(LOGS / (label + '-target.jpg'))
        for _ in range(5):
            client.call('hold_key', dict(text='right', duration=.05))
        for point in ([500, 400], [800, 600]):
            client.call('mouse_move', dict(coordinate=point))
        for _ in range(2):
            client.call('left_click')
        client.call('scroll', dict(scroll_direction='down', scroll_amount=2, coordinate=[800, 600]))
        subprocess.run(['node', str(OUT / 'relative.mjs')], check=True, timeout=30)
        events = m6('hid_read')
        saved(label + '-events.json', events)
        assert sum(e['kind']=='keydown' and e.get('key')==124 for e in events) >= 5
        assert sum(e['kind']=='keyup' and e.get('key')==124 for e in events) >= 5
        assert sum(e['kind']=='mousedown' for e in events) >= 2
        assert sum(e['kind']=='mouseup' for e in events) >= 2
        assert any(e['kind']=='wheel' and e.get('dy') for e in events)
        assert sum(e['kind']=='move' for e in events) >= 4
        client.screenshot(LOGS / (label + '-after.jpg'))
    finally:
        m6('hid_stop')


def cleanup(final=True):
    if (LOGS / 'otg-saved.json').exists():
        info = m6('inspect')
        if info['M6Present']:
            m6('eject')
        lun = remote("from pathlib import Path;print(Path('/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file').read_text().strip())").strip()
        assert not lun, 'Host-owned media remains attached'
        uploaded = LOGS / 'media-upload.json'
        if uploaded.exists():
            identifier = json.loads(uploaded.read_text())['id']
            api('msd/status')
            api('msd/images/'+identifier, 'DELETE')
            uploaded.unlink()
        original = json.loads((LOGS / 'otg-saved.json').read_text())
        alternate = 'full' if original['hid'].get('otg_profile')=='full_no_consumer' else 'full_no_consumer'
        api('config/otg', 'PATCH', dict(hid=dict(original['hid'], otg_profile=alternate), msd=original['msd'], network=original['network'], uac=original['uac'], serial=original['serial']))
        api('config/otg', 'PATCH', dict(hid=original['hid'], msd=original['msd'], network=original['network'], uac=original['uac'], serial=original['serial']))
        bw.ready(HOST, timeout=60)
        (LOGS/'otg-saved.json').unlink()
    if final and (LOGS / 'video-saved.json').exists():
        old = json.loads((LOGS / 'video-saved.json').read_text())
        api('config/video', 'PATCH', dict(output=old['video']['output']))
        api('stream/mode', 'POST', dict(mode=old['mode']['mode']))
        (LOGS/'video-saved.json').unlink()
    if final:bw.ssh(HOST, 'sudo -n /usr/libexec/vim4-edid restore')
    if final and (LOGS / 'm6-probe.log').exists() and not (LOGS/'m6-cleanup.json').exists():
        saved('m6-cleanup.json', m6('cleanup'))



def gate_fan_persistence():
    prior=json.loads((LOGS/'fan-before.json').read_text())
    print(remote('saved_config_hex='+repr(prior)+'\n'+(OUT / 'fan-persistence.py').read_text()))


def gate_hdmi_modes():
    api('config/video', 'PATCH', dict(output=dict(height=0, fps=0, hdr=False)))
    edid = (ASSETS / '1080p60.bin').read_bytes().hex()
    remote("import sys;sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4video;vim4video.set_edid(bytes.fromhex("+repr(edid)+"))")
    time.sleep(2)
    saved('m6-mode-1080.json', m6('mode', width=1920, height=1080))
    saved('hdmi-1080.json', locked(1920, 1080))
    video('hdmi-1080-video', 5, 1920, 1080)
    bw.ssh(HOST, 'sudo -n /usr/libexec/vim4-edid restore')
    time.sleep(2)
    saved('m6-mode-4k.json', m6('mode', width=3840, height=2160))
    saved('hdmi-4k.json', locked(3840, 2160))
    video('hdmi-4k-video', 5)
    remote("import sys;sys.path.insert(0,'/usr/lib/vim4-kvm/python');import vim4video;vim4video.disable_edid()")
    time.sleep(1)
    assert status()['signal'] is False
    state = remote("from pathlib import Path;print(Path('/sys/kernel/debug/fe398000.hdmi-receiver/status').read_text())")
    (LOGS / 'hdmi-no-signal.txt').write_text(state)
    assert 'hpd_request: 0' in state and 'edid_bytes: 0' in state and 'link_ready: 0' in state
    bw.ssh(HOST, 'sudo -n /usr/libexec/vim4-edid restore')
    saved('hdmi-restored.json', locked(3840, 2160))
    video('hdmi-restored-video', 5)
    print('PASS limited 1080p60/4K60/no-signal/recovery; 19-mode matrix NOT RERUN')


def encoder(identifier):
    api('config/video', 'PATCH', dict(output=dict(height=2160, fps=60, hdr=False)))
    api('stream/mode', 'POST', dict(mode=identifier))
    video(identifier, 10, codec='H264' if identifier=='h264' else 'H265')


def gate_h264():
    encoder('h264')


def gate_h265():
    encoder('h265')


def gate_4k60():
    api('config/video','PATCH',dict(output=dict(height=2160,fps=60,hdr=False)))
    api('stream/mode', 'POST', dict(mode='h265'))
    video('motion-4k600', 600, codec='H265')


def gate_audio():
    value = remote("import subprocess;subprocess.run(['systemctl','is-active','vim4-kvm-hdmi','one-kvm'],check=True);subprocess.run(['arecord','-l'],check=True);subprocess.run(['aplay','-l'],check=True)")
    print(value)
    assert 'VIM4HDMIRX' in value


def gate_hid():
    hid('hid')


def gate_media():
    saved('otg-saved.json', api('config/otg'))
    assert not m6('inspect')['M6Present']
    original = json.loads((LOGS / 'otg-saved.json').read_text())
    api('config/otg', 'PATCH', dict(msd=dict(original['msd'], enabled=True)))
    uploaded = saved('media-upload.json', api('upload', 'POST'))
    for readonly in (True, False):
        api('msd/images/'+uploaded['id']+'/mount', 'POST', dict(cdrom=False, read_only=readonly))
        deadline = time.monotonic()+25
        while True:
            info = m6('inspect')
            if info['M6Present']:
                break
            assert time.monotonic()<deadline, 'M6 did not enumerate USB media'
            time.sleep(.5)
        assert info['WritableMedia'] == (not readonly)
        assert info['M6Marker']=='VIM4 edge USB transfer validation'
        if not readonly:
            info = m6('write')
            expected=hashlib.sha256(bytes((i*17+31)&255 for i in range(1024*1024))).hexdigest()
            assert info['M6WrittenSha256']==expected
        saved('media-'+('ro' if readonly else 'rw')+'-host.json', info)
        backing = remote("from pathlib import Path;print(Path('/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file').read_text().strip())").strip()
        m6('eject')
        deadline=time.monotonic()+20
        while remote("from pathlib import Path;print(Path('/sys/kernel/config/usb_gadget/kvm/functions/mass_storage.disk0/lun.0/file').read_text().strip())").strip():
            assert time.monotonic()<deadline, 'SCSI eject did not clear LUN'
            time.sleep(.5)
        api('msd/status')
        if not readonly:
            code='import subprocess,hashlib;data=subprocess.check_output(["mtype","-i",'+repr(backing)+',"::written.bin"]);print(hashlib.sha256(data).hexdigest())'
            assert remote(code).strip()==expected
    cleanup(final=False)
    hid('hid-after-profile-restore')


def gate_gpu():
    text = bw.ssh(HOST, 'sudo -n python3 '+REMOTE+'/run.py --graphics direct -- '+REMOTE+'/gpu-probe 3 /dev/dri/card0', timeout=40)
    print(text)
    assert 'Mali-G52' in text and 'gl_error=0' in text
    assert int(re.search(r'frames=(\d+)', text)[1])>0


def gate_manager():
    subprocess.run(['node', str(OUT / 'fan-check.mjs')], check=True, timeout=75)
    subprocess.run(['node', str(ROOT / 'packaging/kernel/final-manager-check.mjs')], check=True, timeout=90)


def gate_pd():
    # Current formal policy is firmware B state; never probe raw I2C or load TCPM.
    value = api('status')
    program = """from pathlib import Path
import json,re,subprocess
unit=subprocess.check_output(['systemctl','show','vim4-kvm-pd.service','-p','ActiveState','-p','SubState','-p','Result','-p','ConditionResult','-p','ExecMainStatus'],text=True,timeout=5)
print(json.dumps(dict(cmdline=Path('/proc/cmdline').read_text().strip(),
 fusb302_loaded=Path('/sys/module/fusb302').exists(),
 typec_ports=[p.name for p in Path('/sys/class/typec').glob('port*') if re.fullmatch('port[0-9]+',p.name)],
 service=dict(line.split('=',1) for line in unit.splitlines()),
 service_journal=subprocess.check_output(['journalctl','-b','-u','vim4-kvm-pd.service','--no-pager','-o','cat'],text=True,timeout=5))))
"""
    board = json.loads(remote(program))
    saved('pd-state.json', dict(board=board,power=value['power']))
    # Reuse exactly the manager's B-state assertions and tracked expectations.
    code = """import {readFileSync} from 'node:fs';
import {requireFirmwarePDState} from './packaging/kernel/final-manager-pd.mjs';
const x=JSON.parse(readFileSync(process.argv[1]));
requireFirmwarePDState(x.board,x.power,JSON.parse(readFileSync('packaging/kernel/pd-b-state.json')));
"""
    subprocess.run(['node','--input-type=module','-e',code,str(LOGS/'pd-state.json')],check=True,cwd=ROOT)


def gate_decode_smoke():
    archive = ASSETS/'decode-assets.tar'
    upload(archive,REMOTE+'/decode-assets.tar')
    for name in ('smoke.py','hevc-refs.json','decode-smoke.json'):
        upload(OUT/name,REMOTE+'/'+name)
    try:
        print(bw.ssh(HOST, 'sudo -n mkdir '+REMOTE+'/smoke && sudo -n tar xf '+REMOTE+'/decode-assets.tar -C '+REMOTE+'/smoke && sudo -n cp '+REMOTE+'/smoke.py '+REMOTE+'/hevc-refs.json '+REMOTE+'/decode-smoke.json '+REMOTE+'/smoke/ && sudo -n timeout --kill-after=10 360 python3 '+REMOTE+'/smoke/smoke.py '+REMOTE+'/smoke',timeout=380))
    finally:
        subprocess.run(['scp','-q','-r',HOST+':'+REMOTE+'/smoke/results',str(LOGS/'smoke-results')],check=True,timeout=120)


def main():
    global LOGS, HOST, RECEIVER_IP, ASSETS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate',choices=GATES)
    parser.add_argument('--logs',type=Path,required=True)
    parser.add_argument('--plan',type=Path,default=None,help='Defaults to LOGS/plan.json')
    parser.add_argument('--host',default=None)
    parser.add_argument('--receiver-ip',default=None)
    parser.add_argument('--playwright',default=None)
    args=parser.parse_args()
    plan=json.loads((args.plan or args.logs/'plan.json').read_text())
    LOGS=args.logs.resolve();HOST=args.host or plan['host'];RECEIVER_IP=args.receiver_ip or plan['receiver_ip']
    ASSETS=Path(plan['assets'])
    bw.require_board()
    LOGS.mkdir(parents=True,exist_ok=True)
    row=next(row for row in (ROOT/'docs/hardware.md').read_text().splitlines() if row.startswith('| admin |'))
    os.environ.update(MANAGER_PASSWORD=row.split('|')[2].strip().strip('`'),
                      PLAYWRIGHT_MODULE=args.playwright or plan['playwright'],
                      VIM4_TEST_CHROME=os.environ.get('VIM4_TEST_CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                      VIM4_FINAL_LOGS=str(LOGS),VIM4_HOST=HOST,VIM4_EXPECTED_RELEASE=plan['release'],
                      VIM4_MEDIA_IMAGE=str(ASSETS/'usb-edge-transfer.img'))
    os.environ.setdefault('MANAGER_URL','http://127.0.0.1:18080')
    for path, expected in plan['files'].items():
        with Path(path).open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==expected, 'Plan input changed: '+path
    with gate_tunnel():
        if args.gate not in ('fan-persistence','cleanup','decode-smoke','pd') and not (LOGS/'video-saved.json').exists():
            saved('video-saved.json',dict(video=api('config/video'),mode=api('stream/mode')))
        if args.gate=='gpu':
            for source,target in ((ASSETS/'gpu-probe','gpu-probe'),(ROOT/'packaging/kbase/run.py','run.py')):
                upload(source,REMOTE+'/'+target)
            bw.ssh(HOST,'chmod +x '+REMOTE+'/gpu-probe')
        GATES[args.gate]()


GATES = {
    'fan-persistence': gate_fan_persistence,
    'hdmi-modes': gate_hdmi_modes,
    'h264': gate_h264,
    'h265': gate_h265,
    '4k60': gate_4k60,
    'audio': gate_audio,
    'hid': gate_hid,
    'media': gate_media,
    'gpu': gate_gpu,
    'manager': gate_manager,
    'cleanup': cleanup,
    'pd': gate_pd,
    'decode-smoke': gate_decode_smoke,
}

if __name__ == '__main__':
    main()

