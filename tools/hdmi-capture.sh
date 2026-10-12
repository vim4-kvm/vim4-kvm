#!/bin/sh
# Grab one HDMI-in frame through vfm_cap (standalone, vdin0 -> vfm_cap) as PNG.
#
# Usage (on the board): sudo sh hdmi-capture.sh [out.png]
# Needs test_dmabuf built from common_drivers drivers/media/vfm_cap/test_dmabuf.c
# in the same directory as this script.
set -eu

OUT=${1:-/tmp/hdmi.png}
DIR=$(cd "$(dirname "$0")" && pwd)
MAP=/sys/class/vfm/map

modprobe vfm_cap
# 8-bit write: the default 10-bit 4K mode produces Amlogic packed AMLY
echo "color_depth_support 0x1" > /sys/class/vdin/vdin0/attr

if ! grep -q 'tvpath.*vfm_cap' $MAP; then
	pkill hdmiin-demo || true
	sleep 2
	echo "rm tvpath" > $MAP
	sleep 0.2
	echo "add tvpath vdin0 vfm_cap" > $MAP
fi
pgrep hdmiin-demo >/dev/null || {
	setsid hdmiin-demo </dev/null >/tmp/hdmiin.log 2>&1 &
	sleep 8
}

DEV=/dev/$(basename "$(dirname "$(grep -l vfm_cap /sys/class/video4linux/*/name)")")
FMT=$(v4l2-ctl -d "$DEV" -V)
W=$(echo "$FMT" | sed -n 's#.*Width/Height *: *\([0-9]*\)/.*#\1#p')
H=$(echo "$FMT" | sed -n 's#.*Width/Height *: *[0-9]*/\([0-9]*\).*#\1#p')
case $(echo "$FMT" | sed -n "s#.*Pixel Format *: *'\(....\)'.*#\1#p") in
UYVY) PIX=uyvy422 ;;
NV21) PIX=nv21 ;;
NV12) PIX=nv12 ;;
*) echo "unsupported format:"; echo "$FMT"; exit 1 ;;
esac

"$DIR/test_dmabuf" 5 "$DEV" /tmp/hdmi.raw >/dev/null
ffmpeg -loglevel error -y -f rawvideo -pix_fmt $PIX -s ${W}x$H \
	-i /tmp/hdmi.raw -frames:v 1 "$OUT"
echo "$OUT (${W}x$H $PIX)"
