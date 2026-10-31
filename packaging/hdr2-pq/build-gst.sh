#!/bin/sh
# Private plugin; never install system files or contact the board.
set -eu
recipe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$1
python3 "$recipe/../kernel-edge/build-gstreamer.py" "$work"
