#!/usr/bin/env python3
"""Build a private stateless decoder plugin in an empty Linux ARM64 directory.

Usage: build-vdec-gstreamer.py WORK_DIRECTORY
No system plugins, board files or services are changed.
"""
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request


def main():
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise SystemExit('Requires Linux ARM64 with GStreamer development packages')
    recipe = Path(__file__).resolve().parent
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('Use an empty work directory')
    locked = tomllib.loads((recipe / 'vdec-gstreamer.toml').read_text())
    archive = work / 'source.tar.xz'
    with urllib.request.urlopen(locked['source_url'], timeout=60) as response, archive.open('wb') as output:
        shutil.copyfileobj(response, output)
    with archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != locked['source_sha256']:
            raise SystemExit('GStreamer archive checksum mismatch')
    with tarfile.open(archive) as source:
        source.extractall(work, filter='data')
    tree = work / locked['source_directory']
    for patch in locked['patches']:
        subprocess.run(['patch', '-p1', '--forward', '-i', str(recipe / patch)], cwd=tree, check=True)
    subprocess.run([sys.executable, str(recipe / 'test_gstreamer_mpeg2.py'),
                    str(tree / 'sys/v4l2codecs/gstv4l2codecmpeg2dec.c')], check=True)
    subprocess.run(['meson', 'setup', 'build', '-Dauto_features=disabled',
                    '-Dv4l2codecs=enabled', '-Dtests=disabled', '-Dexamples=disabled',
                    '-Ddoc=disabled', '-Dnls=disabled'], cwd=tree, check=True)
    subprocess.run(['meson', 'compile', '-C', 'build', '-j', '8'], cwd=tree, check=True)
    stage = work / 'stage'
    subprocess.run(['meson', 'install', '-C', 'build', '--no-rebuild',
                    '--destdir', str(stage)], cwd=tree, check=True)
    plugins = list(stage.rglob('libgstv4l2codecs.so'))
    if len(plugins) != 1:
        raise SystemExit('Expected exactly one installed decoder plugin')
    shutil.copy2(plugins[0], work / 'libgstv4l2codecs.so')


if __name__ == '__main__':
    main()
