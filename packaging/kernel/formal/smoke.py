#!/usr/bin/env python3
"""Board side: DOS regmap debugfs power gating, then a short decode smoke."""
import errno, hashlib, json, os, subprocess, sys, time
from pathlib import Path

root = Path(sys.argv[1]); out = root/'results'; out.mkdir()
JPEG = json.loads((root/'decode-smoke.json').read_text())['jpeg']
DEVICE = Path('/sys/bus/platform/devices/fe320000.video-codec')
result = dict(steps=[])

def save():
    (out/'smoke.json').write_text(json.dumps(result, indent=2) + '\n')

def step(name, **value):
    result['steps'].append(dict(name=name, at=time.monotonic(), **value)); save()

def run(*argv, timeout=30):
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=timeout).stdout

def runtime_status():
    return (DEVICE/'power/runtime_status').read_text().strip()

def registers(label):
    paths = sorted(Path('/sys/kernel/debug/regmap').glob('fe320000.video-codec*'))
    assert len(paths) == 1, paths
    text = (paths[0]/'registers').read_text()
    (out/(label + '-registers.txt')).write_text(text)
    rows = [line.split(': ') for line in text.splitlines()]
    addresses = [int(a, 16) for a, _ in rows]
    assert addresses == list(range(0xfc00, 0x10000, 4)), (addresses[:2], addresses[-2:], len(addresses))
    hidden = sum(v == 'XXXXXXXX' for _, v in rows)
    return dict(rows=len(rows), hidden=hidden, runtime=runtime_status(),
                sw_reset0=rows[0][1], gclk_en0=rows[1][1])

def nodes():
    return {p.read_text().strip(): '/dev/' + p.parent.name
            for p in Path('/sys/class/video4linux').glob('video*/name')}

def kernel_since(cursor):
    text = run('journalctl', '-k', '--no-pager', '-o', 'short-monotonic', '--after-cursor', cursor)
    bad = [l for l in text.splitlines() if any(k in l for k in ('WARNING:', 'BUG:', 'Oops', 'Unable to handle',
                                                                  'SError', 'Internal error', 'Call trace'))]
    return text, bad

def bindings():
    driver = DEVICE/'driver'
    return dict(decoder=str(driver.resolve()) if driver.exists() else None,
                wave5=Path('/sys/module/wave5').is_dir(), t7_jpeg=Path('/sys/module/t7_jpeg').is_dir())

def capture(name, pipeline, target, frames, timeout=40):
    env = dict(os.environ, GST_PLUGIN_PATH=f'{root}/tools/official:{root}/tools/plugins',
               GST_REGISTRY=str(root/(name + '.registry')), GST_DEBUG_NO_COLOR='1')
    with (out/(name + '.log')).open('w') as log:
        code = subprocess.run([str(root/'tools/bin/vdec-capture'), pipeline, str(target), str(frames)],
                              stdout=log, stderr=subprocess.STDOUT, env=env, timeout=timeout).returncode
    text = (out/(name + '.log')).read_text()
    return code, f'Captured {frames} frames; status 0' in text

cursor = run('journalctl', '-k', '-n', '0', '--show-cursor', '--no-pager').strip().split('cursor: ')[-1]
try:
    devices = nodes(); step('nodes', nodes=devices, bindings=bindings())
    decoder = devices['aml_dev_drv']
    step('idle', registers=registers('idle'))
    assert result['steps'][-1]['registers']['hidden'] == 256, 'Idle DOS-top must stay unread'
    try:
        fd = os.open(decoder, os.O_RDWR | os.O_NONBLOCK)
    except OSError as error:
        busy = error.errno
    else:
        os.close(fd); busy = 0
    step('encoder-loaded-open', errno=busy, registers=registers('busy'))
    assert busy == errno.EBUSY, 'Decoder open must be EBUSY while encoders own DOS'
    assert result['steps'][-1]['registers']['hidden'] == 256
    run('systemctl', 'stop', 'one-kvm')
    run('modprobe', '-r', 'wave5', 't7_jpeg')
    step('encoders-unloaded', bindings=bindings())
    fd = os.open(decoder, os.O_RDWR | os.O_NONBLOCK)
    try:
        step('open', registers=registers('open'))
    finally:
        os.close(fd)
    step('closed', registers=registers('closed'))
    opened, closed = (s['registers'] for s in result['steps'][-2:])
    assert opened['hidden'] == 0 and opened['runtime'] == 'active', opened
    assert closed['hidden'] == 256 and closed['runtime'] == 'suspended', closed
    hevc = devices['aml_hevc_decoder']
    for ref in json.loads((root/'hevc-refs.json').read_text()):
        source = root/'streams'/ref['input_path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == ref['input_sha256']
        target = out/(ref['name'] + '.i420')
        code, status = capture(ref['name'], f'filesrc location="{source}" ! h265parse ! v4l2h265dec ! '
                               'videoconvert ! video/x-raw,format=I420 ! appsink name=capture', target, ref['frames'])
        data = target.read_bytes() if target.exists() else b''
        size = ref['reference_bytes'] // ref['frames']
        frames = [hashlib.md5(data[i:i + size]).hexdigest() for i in range(0, len(data), size)]
        row = dict(exit=code, status_zero=status, bytes=len(data), frames=len(frames),
                   frame_match=frames == ref['frame_md5'], total_md5=hashlib.md5(data).hexdigest(),
                   publisher_md5=ref['publisher_md5'], registers=registers(ref['name']))
        step('hevc-' + ref['name'], **row)
        assert code == 0 and status and row['frame_match'] and row['total_md5'] == ref['publisher_md5'], ref['name']
        target.unlink()
    for name, (size, digest) in JPEG.items():
        target = out/(name + '.i420')
        code, status = capture(name, f'filesrc location="{root}/streams/jpeg-fixtures/{name}.mjpg" ! jpegparse ! '
                               'v4l2jpegdec ! videoconvert ! video/x-raw,format=I420 ! appsink name=capture', target, 16)
        data = target.read_bytes() if target.exists() else b''
        row = dict(exit=code, status_zero=status, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                   registers=registers(name))
        step('jpeg-' + name, **row)
        assert code == 0 and status and (len(data), row['sha256']) == (size, digest), name
        target.unlink()
    result['decode_passed'] = True
finally:
    # Restore the KVM application whatever happened above.
    restore = {}
    for name in ('wave5', 't7_jpeg'):
        restore[name] = subprocess.run(['modprobe', name], capture_output=True, text=True, timeout=20).returncode
    subprocess.run(['udevadm', 'settle', '--timeout=5'], timeout=8)
    restore['one-kvm'] = subprocess.run(['systemctl', 'start', 'one-kvm'], capture_output=True, text=True, timeout=40).returncode
    time.sleep(3)
    restore['active'] = subprocess.run(['systemctl', 'is-active', 'one-kvm'], capture_output=True, text=True).stdout.strip()
    restore['bindings'] = bindings(); restore['nodes'] = nodes()
    restore['after'] = registers('restored')
    text, bad = kernel_since(cursor)
    (out/'kernel.log').write_text(text)
    result.update(restore=restore, kernel_faults=bad)
    save()
assert not result['kernel_faults'] and result['restore']['active'] == 'active'
assert result['restore']['after']['hidden'] == 256
assert result['restore']['bindings']['wave5'] and result['restore']['bindings']['t7_jpeg']
print(json.dumps(result))

