#!/usr/bin/env python3
"""Build the pinned private V4L2 plugin in an empty Linux ARM64 directory.

Usage: build-gstreamer.py WORK_DIRECTORY
Downloads are checked before extraction; system GStreamer files are not changed.
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
        raise SystemExit('Requires the Linux ARM64 GStreamer development environment')
    recipe = Path(__file__).resolve().parent
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('Use an empty work directory')
    locked = tomllib.loads((recipe / 'sources.toml').read_text())['gstreamer']
    archive = work / 'source.tar.xz'
    with urllib.request.urlopen(locked['source_url'], timeout=60) as response, archive.open('wb') as output:
        shutil.copyfileobj(response, output)
    with archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != locked['source_sha256']:
            raise SystemExit('GStreamer archive checksum mismatch')
    with tarfile.open(archive) as source:
        source.extractall(work, filter='data')
    tree = work / 'gst-plugins-good-1.24.2'
    for patch in locked['patches']:
        subprocess.run(['patch', '-p1', '--forward', '-i', str(recipe / patch)], cwd=tree, check=True)
    subprocess.run([sys.executable, str(recipe / 'test_gstreamer_orphan.py'),
                    str(tree / 'sys/v4l2/gstv4l2bufferpool.c')], check=True)
    subprocess.run(['meson', 'setup', 'build', '-Dauto_features=disabled', '-Dv4l2=enabled',
                    '-Dtests=disabled', '-Dexamples=disabled', '-Ddoc=disabled', '-Dnls=disabled'],
                   cwd=tree, check=True)
    subprocess.run(['meson', 'compile', '-C', 'build'], cwd=tree, check=True)
    shutil.copy2(tree / 'build/sys/v4l2/libgstvideo4linux2.so', work / 'libgstvideo4linux2.so')


if __name__ == '__main__':
    main()
