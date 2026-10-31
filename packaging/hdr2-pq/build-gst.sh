#!/bin/sh
# Private plugin; never install system files or contact the board.
set -eu
recipe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$1
python3 "$recipe/../kernel-edge/build-gstreamer.py" "$work"
tree="$work/gst-plugins-good-1.24.2"
patch -d "$tree" -p1 < "$recipe/gstreamer-srgb-probe.patch"
patch -d "$tree" -p1 < "$recipe/gstreamer-encoded-size.patch"
python3 "$recipe/test_gst_color.py" "$tree/sys/v4l2/gstv4l2object.c"
python3 "$recipe/test_gst_size.py" "$tree/sys/v4l2/gstv4l2object.c"
meson compile -C "$tree/build"
cp "$tree/build/sys/v4l2/libgstvideo4linux2.so" "$work/libgstvideo4linux2.so"
