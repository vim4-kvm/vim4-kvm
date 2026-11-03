#!/usr/bin/env python3
"""Offline FFmpeg adapter for this workspace's ARM64 build VM.

Only the explicit input file is sent on stdin; FFmpeg never traverses a shared
Mac directory. Invoke through board-queue --heavy, after the board window.
"""
from pathlib import Path
import subprocess
import sys

args=sys.argv[1:]
data=None
if '-i' in args:
    index=args.index('-i')+1
    data=Path(args[index]).read_bytes()
    args[index]='pipe:0'
raise SystemExit(subprocess.run(['orb','-m','vim4-build','-w','/home/deepdream',
    'ffmpeg',*args],input=data).returncode)
