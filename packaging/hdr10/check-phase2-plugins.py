#!/usr/bin/env python3
"""Inspect the assembled private plugin directory without starting a pipeline.

Device-created V4L2 encoder factories are checked again on the RAM candidate;
they cannot be registered on a build host without its capture/encoder nodes.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

PRIVATE = {
    'vim4h265src':'libgstvim4hevc10.so', 'vim4hevc10enc':'libgstvim4hevc10.so',
    'vim4amlysrc':'libgstvfmcap.so', 'vim4pq2sdr':'libgstvfmcap.so',
    'vim4v4l2src':'libgstvim4wave5.so', 'vim4wave5enc':'libgstvim4wave5.so',
    'vim4jpegenc':'libgstvim4jpegenc.so', 'v4l2src':'libgstvideo4linux2.so',
}
# Actual Wave5/native/snapshot bins used by the four applications.
COMMON = ('appsrc','appsink','queue','tee','valve','videorate','capsfilter',
          'h265parse','h264parse','videoconvert','videoscale','jpegenc')
DEVICE = ('v4l2h265enc','v4l2h264enc')


def check(directory, device_factories=False):
    directory=directory.resolve()
    for library in set(PRIVATE.values()):
        if not (directory/library).is_file(): raise ValueError('missing private plugin: '+library)
    expected=dict(PRIVATE)
    if device_factories: expected.update({name:'libgstvideo4linux2.so' for name in DEVICE})
    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ,GST_PLUGIN_PATH=str(directory),GST_PLUGIN_PATH_1_0=str(directory),
            GST_REGISTRY=str(Path(tmp)/'registry.bin'),GST_DEBUG_NO_COLOR='1')
        for name in (*expected,*COMMON):
            result=subprocess.run(['gst-inspect-1.0',name],env=env,capture_output=True,text=True,timeout=15)
            if result.returncode: raise ValueError('unavailable factory: '+name+'\n'+result.stderr)
            if name in expected:
                match=re.search(r'^\s*Filename\s+(.+)$',result.stdout,re.M)
                if not match or Path(match[1]).resolve()!=directory/expected[name]:
                    raise ValueError('factory resolved outside assembled plugin directory: '+name)
    return dict(private_factories=list(expected),common_factories=list(COMMON),
        device_factories_unverified=[] if device_factories else list(DEVICE))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--device-factories',action='store_true')
    args=parser.parse_args();print(json.dumps(check(args.directory,args.device_factories)))
