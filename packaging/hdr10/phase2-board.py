#!/usr/bin/env python3
"""Board half of the P0-5 window. Only called by phase2-window with its ticket.

Saves exact bytes/ownership before temporary video settings. Does not enable
services, change boot files, touch HID, test sound or access MMIO.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

UNITS = {'onekvm':'one-kvm.service','nanokvm':'nanokvm.service',
         'jetkvm':'vim4-kvm.service','pikvm':'vim4-pikvm.service'}
FILES = ['/etc/default/vim4-kvm-hdr','/etc/kvm/video.json','/var/lib/jetkvm/config.json',
         '/var/lib/kvmd/video-codec','/var/lib/kvmd/video-output-height']

# include/uapi/linux/v4l2-controls.h; t7-vdin-test registers these standard IDs.
V4L2_CTRL_CLASS_COLORIMETRY = 0x00a50000
V4L2_CID_COLORIMETRY_CLASS_BASE = V4L2_CTRL_CLASS_COLORIMETRY | 0x900
V4L2_CID_COLORIMETRY_HDR10_CLL_INFO = V4L2_CID_COLORIMETRY_CLASS_BASE + 0
V4L2_CID_COLORIMETRY_HDR10_MASTERING_DISPLAY = V4L2_CID_COLORIMETRY_CLASS_BASE + 1


def stop():
    subprocess.run(['systemctl','stop',*UNITS.values()],check=True,timeout=25)


def api(path, value=None, method=None):
    request = urllib.request.Request('http://127.0.0.1:8081/api/'+path,
        data=None if value is None else json.dumps(value).encode(),
        headers={'Content-Type':'application/json'},method=method)
    return json.load(urllib.request.urlopen(request,timeout=15))


def status():
    import re
    return dict(taint=int(Path('/proc/sys/kernel/tainted').read_text()),
        cma={k:int(v) for k,v in re.findall(r'^(Cma\w+):\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)})


def metadata():
    """Read HDMI controls only; do not allocate or stream capture buffers."""
    import ctypes as c
    import fcntl
    class Control(c.Structure):
        _pack_=1
        _fields_=[('id',c.c_uint32),('size',c.c_uint32),('reserved',c.c_uint32),('ptr',c.c_void_p)]
    class Controls(c.Structure):
        _fields_=[('which',c.c_uint32),('count',c.c_uint32),('error',c.c_uint32),
            ('request',c.c_int32),('reserved',c.c_uint32),('controls',c.POINTER(Control))]
    class Mastering(c.Structure):
        _fields_=[('x',c.c_uint16*3),('y',c.c_uint16*3),('wx',c.c_uint16),('wy',c.c_uint16),
            ('maximum',c.c_uint32),('minimum',c.c_uint32)]
    class Cll(c.Structure):
        _fields_=[('maximum',c.c_uint16),('fall',c.c_uint16)]
    nodes=[p.parent.name for p in Path('/sys/class/video4linux').glob('video*/name')
        if p.read_text().strip()=='t7-vdin-test']
    if len(nodes)!=1: raise ValueError('expected one VDIN capture node')
    mastering,cll=Mastering(),Cll()
    controls=(Control*2)(Control(V4L2_CID_COLORIMETRY_HDR10_MASTERING_DISPLAY,
        c.sizeof(mastering),0,c.addressof(mastering)),
        Control(V4L2_CID_COLORIMETRY_HDR10_CLL_INFO,c.sizeof(cll),0,c.addressof(cll)))
    query=Controls();query.count=2;query.controls=controls
    fd=os.open('/dev/'+nodes[0],os.O_RDONLY|os.O_NONBLOCK)
    try: fcntl.ioctl(fd,0xc0205647,query)
    finally: os.close(fd)
    return dict(primaries=list(zip(mastering.x,mastering.y)),white=[mastering.wx,mastering.wy],
        luminance=[mastering.maximum,mastering.minimum],cll=[cll.maximum,cll.fall])


def plugins():
    import sys
    init=next(word[5:] for word in Path('/proc/cmdline').read_text().split() if word.startswith('init='))
    runtime=Path(init).parent/'runtime'
    subprocess.run([sys.executable,str(runtime/'check-phase2-plugins.py'),str(runtime/'gstreamer-1.0'),
        '--device-factories'],check=True,timeout=60)


def save(path):
    if path.exists(): raise ValueError('checkpoint already exists')
    records={}
    for name in FILES:
        file=Path(name)
        if file.exists():
            info=file.stat()
            records[name]=dict(data=file.read_bytes().hex(),mode=info.st_mode & 0o777,uid=info.st_uid,gid=info.st_gid)
        else: records[name]=None
    records['onekvm_video']=api('config/video')
    records['onekvm_mode']=api('stream/mode')['mode']
    path.write_text(json.dumps(records)); path.chmod(0o600)


def configure(path, app, height, hdr):
    stop()
    policy=Path('/etc/default/vim4-kvm-hdr')
    import re
    text=policy.read_text() if policy.exists() else ''
    text=re.sub(r'^\s*HDR_SDR_ENABLED=.*$', '', text, flags=re.M)
    policy.write_text(text+f'\nHDR_SDR_ENABLED={0 if hdr else 1}\n')
    if app=='nanokvm':
        file=Path('/etc/kvm/video.json'); config=json.loads(file.read_text())
        config.update(width=3840 if not height else 1920,height=height or 2160,fps=60)
        file.write_text(json.dumps(config))
    elif app=='jetkvm':
        file=Path('/var/lib/jetkvm/config.json'); config=json.loads(file.read_text())
        config.update(video_codec_preference='h265',video_output_height=height)
        file.write_text(json.dumps(config))
    elif app=='pikvm':
        Path('/var/lib/kvmd/video-codec').write_text('h265\n')
        Path('/var/lib/kvmd/video-output-height').write_text(str(height)+'\n')
    subprocess.run(['/usr/libexec/vim4-manager-helper','restart',UNITS[app]],check=True,timeout=40)
    deadline=time.monotonic()+25
    while True:
        try:
            urllib.request.urlopen('http://127.0.0.1:8081/',timeout=2).close()
            break
        except (OSError,TimeoutError):
            if time.monotonic()>deadline: raise
            time.sleep(.2)
    if app=='onekvm':
        api('config/video',dict(output=dict(height=height,fps=60,hdr=hdr)), 'PATCH')
        api('stream/mode',dict(mode='h265'),'POST')
    print(json.dumps(status()))


def restore(path):
    records=json.loads(path.read_text()); stop()
    for name in FILES:
        file=Path(name); record=records[name]
        if record is None: file.unlink(missing_ok=True)
        else:
            file.write_bytes(bytes.fromhex(record['data']))
            os.chown(file,record['uid'],record['gid']); file.chmod(record['mode'])
    subprocess.run(['systemctl','start',UNITS['onekvm']],check=True,timeout=30)
    deadline=time.monotonic()+25
    while True:
        try:
            api('config/video',records['onekvm_video'],'PATCH')
            api('stream/mode',dict(mode=records['onekvm_mode']),'POST')
            break
        except (OSError,TimeoutError):
            if time.monotonic()>deadline: raise
            time.sleep(.2)
    # The config API can rewrite the shared policy file; restore its exact bytes.
    for name in FILES:
        record=records[name]; file=Path(name)
        if record is not None:
            file.write_bytes(bytes.fromhex(record['data']))
            os.chown(file,record['uid'],record['gid']); file.chmod(record['mode'])
        elif file.exists(): file.unlink()
    print(json.dumps(dict(restored=True,sha256={n:hashlib.sha256(Path(n).read_bytes()).hexdigest()
        if Path(n).exists() else None for n in FILES})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('save','configure','restore','status','stop','metadata','plugins'))
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--app',choices=UNITS,default='onekvm')
    parser.add_argument('--height',type=int,choices=(0,1080),default=0)
    parser.add_argument('--hdr',choices=('on','off'),default='on')
    args=parser.parse_args()
    if args.operation=='save': save(args.checkpoint)
    elif args.operation=='restore': restore(args.checkpoint)
    elif args.operation=='configure': configure(args.checkpoint,args.app,args.height,args.hdr=='on')
    elif args.operation=='stop': stop(); print(json.dumps(status()))
    elif args.operation=='metadata': print(json.dumps(metadata()))
    elif args.operation=='plugins': plugins()
    else: print(json.dumps(status()))
