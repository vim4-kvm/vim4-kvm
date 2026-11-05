#!/usr/bin/env python3
"""Build Fluster's locked ISO MPEG-2 oracle on Linux ARM64, offline and private.

The user must obtain the licensed source separately. This builds only the video
reference decoder, with Fluster's Meson recipe; it does not install or distribute
the source or executable and never accesses the board.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--fluster', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.uname().sysname != 'Linux' or os.uname().machine != 'aarch64':
        parser.error('Build on Linux ARM64')
    lock = tomllib.loads(Path(__file__).with_name('vdec-fluster.toml').read_text())
    reference = lock['mpeg2_reference']
    if sha(args.source_archive) != reference['source_sha256']:
        raise ValueError('ISO source archive differs from lock')
    revision = subprocess.check_output(['git', '-C', str(args.fluster), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(args.fluster), 'status', '--porcelain'], text=True).strip()
    if revision != lock['revision'] or dirty:
        raise ValueError('Fluster recipe checkout must be clean and locked')
    args.output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.source_archive) as archive:
        video = archive.read(reference['archive_member'])
    with zipfile.ZipFile(io.BytesIO(video)) as archive:
        archive.extractall(args.output)
    source = args.output / 'video'
    recipe = args.fluster / reference['meson_recipe']
    shutil.copyfile(recipe, source / 'meson.build')
    build = args.output / 'build'
    subprocess.run(['meson', 'setup', str(build), str(source)], check=True)
    subprocess.run(['meson', 'compile', '-C', str(build), '-j', '2'], check=True)
    binary = build / 'mpeg2decode'
    report = dict(source_sha256=sha(args.source_archive), fluster_revision=revision,
                  meson_sha256=sha(recipe), binary_sha256=sha(binary),
                  compiler=subprocess.check_output(['cc', '--version'], text=True).splitlines()[0],
                  linked_libraries=subprocess.check_output(['ldd', str(binary)], text=True),
                  validation='compiled; codec conformance not yet tested')
    (args.output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
