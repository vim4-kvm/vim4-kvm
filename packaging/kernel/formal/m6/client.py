"""Temporary M6 fixture client, downloaded via the reviewed terminal command."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
SERVER = os.environ.get('VIM4_M6_SERVER', 'http://192.168.50.239:18274')
hostname = subprocess.check_output(['hostname'], text=True).strip()
assert hostname.split('.')[0].lower() == 'deepdremsminim6', hostname
children = {}
displays = json.loads(subprocess.check_output([ROOT / 'hdmi-source-mode', 'list'], text=True))
display = next(row for row in displays if row['vendor'] == 19083)
original = display['current']
original_source=subprocess.check_output([ROOT/'input-source'],text=True).strip()
subprocess.run([ROOT/'input-source','com.apple.keylayout.US'],check=True)


def stop(name):
    if name not in children:
        return
    process, stream = children.pop(name)
    if name == 'hid':
        process.stdin.close()
    else:
        process.terminate()
    process.wait(timeout=10)
    stream.close()


def action(job):
    name = job['action']
    if name == 'probe':
        return dict(hostname=hostname,original_input_source=original_source,selected_input_source=subprocess.check_output([ROOT/'input-source'],text=True).strip(), displays=json.loads(subprocess.check_output([ROOT / 'hdmi-source-mode', 'list'], text=True)))
    if name == 'mode':
        rows = json.loads(subprocess.check_output([ROOT / 'hdmi-source-mode', 'list'], text=True))
        row = next(row for row in rows if row['vendor'] == 19083)
        modes = [m for m in row['modes'] if m['pixelWidth'] == job['width'] and m['pixelHeight'] == job['height'] and abs(m['hz']-60) < 1]
        assert modes, 'Requested native 60Hz backing raster unavailable'
        chosen = min(modes, key=lambda m: (m['width'] != m['pixelWidth'], abs(m['hz']-60)))
        return json.loads(subprocess.check_output([ROOT / 'hdmi-source-mode', 'set', str(row['display']), str(chosen['id'])], text=True))
    if name in ('hid_start', 'source_start'):
        kind = name.split('_')[0]
        assert kind not in children
        stream = (ROOT / (kind + '.jsonl')).open('w')
        argv = [str(ROOT / 'input-target'), '90'] if kind == 'hid' else [str(ROOT / 'latency-source'), '780', '--motion', '--verify-coherence', '--no-labels']
        env = dict(os.environ, VIM4_HDMI_DISPLAY='RTK')
        process = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE, stdout=stream, stderr=stream)
        children[kind] = (process, stream)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            assert process.poll() is None, (ROOT / (kind + '.jsonl')).read_text()
            data = (ROOT / (kind + '.jsonl')).read_text()
            if data.strip():
                return dict(pid=process.pid, output=data)
            time.sleep(.1)
        raise TimeoutError('Native fixture did not become ready')
    if name == 'hid_read':
        return [json.loads(row) for row in (ROOT / 'hid.jsonl').read_text().splitlines()]
    if name in ('hid_stop', 'source_stop'):
        kind=name.split('_')[0]
        stop(kind)
        return dict(stopped=True, output=(ROOT/(kind+'.jsonl')).read_text())
    if name in ('inspect', 'write', 'eject'):
        text = subprocess.check_output(['python3', ROOT / 'host.py', name], text=True, timeout=25)
        return dict(output=text) if name == 'eject' else json.loads(text)
    if name == 'cleanup':
        for kind in list(children):
            stop(kind)
        rows = json.loads(subprocess.check_output([ROOT / 'hdmi-source-mode', 'list'], text=True))
        row = next(row for row in rows if row['vendor'] == 19083)
        if row['current'] != original:
            subprocess.run([ROOT / 'hdmi-source-mode', 'set', str(row['display']), str(original)], check=True)
        subprocess.run([ROOT/'input-source',original_source],check=True)
        return dict(cleaned=True, original_mode=original,restored_input_source=subprocess.check_output([ROOT/'input-source'],text=True).strip(),client_exiting=True)
    raise ValueError(name)


deadline = time.monotonic() + 2700
try:
    while time.monotonic() < deadline:
        job = json.load(urllib.request.urlopen(SERVER + '/next', timeout=10))
        if not job:
            time.sleep(.25)
            continue
        try:
            reply = dict(id=job['id'], ok=True, result=action(job))
        except Exception as error:
            reply = dict(id=job['id'], ok=False, error=repr(error))
        request = urllib.request.Request(SERVER + '/result', data=json.dumps(reply).encode(), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=10).read()
        if job['action']=='cleanup':break
finally:
    for kind in list(children):
        stop(kind)

