#!/bin/sh
# Set up the HDMI-in capture path for the KVM:
#   HDMI RX port 1 -> vdin0 (8-bit NV21, hw scaled) -> vfm_cap (standalone)
# then open the source through tvserver (hdmiin-demo) and keep it open.
#
# Usage: hdmi-setup.sh [WIDTH HEIGHT]     (default 3840 2160)
# Runs as root (vim4-kvm-hdmi.service).
set -eu

W=${1:-${HDMI_WIDTH:-3840}}
H=${2:-${HDMI_HEIGHT:-2160}}
LOW_LATENCY=${HDMI_LOW_LATENCY:-1}
CAPTURE_FORMAT=${HDMI_CAPTURE_FORMAT:-NV21}
case "$CAPTURE_FORMAT" in
	NV21) CONVERSION=8 ;;
	YUV444) CONVERSION=2 ;;
	*) echo "HDMI_CAPTURE_FORMAT must be NV21 or YUV444" >&2; exit 2 ;;
esac
case "$LOW_LATENCY" in
	0|1) ;;
	*) echo "HDMI_LOW_LATENCY must be 0 or 1" >&2; exit 2 ;;
esac
case "$W:$H" in
	3840:2160|1920:1080|1280:720) ;;
	*) echo "Unsupported capture size: $W x $H (use 3840x2160, 1920x1080 or 1280x720)" >&2; exit 2 ;;
esac
# HDR10 -> SDR mapping (vim4-hdr-curve); defaults are BT.2408 reference white
# and a 1000-nit highlight range. vim4-manager writes /etc/default/vim4-kvm-hdr.
SDR_WHITE=${HDR_SDR_WHITE:-203}
SDR_PEAK=${HDR_SDR_PEAK:-1000}
HDR_CURVE=$(dirname "$0")/vim4-hdr-curve
MAP=/sys/class/vfm/map
VDIN=/sys/class/vdin/vdin0/attr
NATIVE_HDR=0
if [ -r /sys/module/aml_media/parameters/vdin0_native_hdr ] &&
    [ "$(cat /sys/module/aml_media/parameters/vdin0_native_hdr)" = Y ]; then
    NATIVE_HDR=1
    CONVERSION=1
fi

modprobe vfm_cap
# Invalid values stop the service, like the capture size checks above; a
# kernel without the tables (exit 3) keeps the vendor curves.
"$HDR_CURVE" apply "$SDR_WHITE" "$SDR_PEAK" || [ $? = 3 ]

# tvserver reloads its vendor EDID set at boot; reapply the EDID selected in
# NanoKVM (if any) before the host reads it. A failure keeps the vendor EDID.
if [ -x /usr/libexec/vim4-edid ]; then
	/usr/libexec/vim4-edid restore || echo "EDID restore failed; keeping vendor EDID" >&2
fi

pkill -x hdmiin-demo 2>/dev/null && sleep 2 || true

# 8-bit only: the 4K 10-bit default is Amlogic packed 422 (AMLY)
if [ "$NATIVE_HDR" = 1 ]; then
    echo "color_depth_support 0x235" > $VDIN
    echo "color_depth 10" > $VDIN
else
    echo "color_depth_support 0x1" > $VDIN
    echo "color_depth 8" > $VDIN
fi
# linear little-endian writes, as the CPU/encoder read them
echo "no_swap_en 1" > $VDIN
# Capture is shared by every viewer. YUV444 requires a compatible downstream
# pipeline; changing it is a service configuration, not a per-session option.
echo "conversion $W $H $CONVERSION" > $VDIN

# BIT0 | BIT1 selects completed-frame game mode 1. With RDMA, the normal
# path otherwise retains the finished frame until the following interrupt.
# Never enable BIT2: its same-buffer read/write path is unsafe for DMA-buf
# consumers without additional synchronization. Zero restores vendor policy.
if [ "$LOW_LATENCY" = 1 ]; then
	echo "game_mode 3" > $VDIN
else
	echo "game_mode 0" > $VDIN
fi

if [ "${HDMI_DISPLAY_TEE:-0}" = 1 ] && /usr/libexec/vim4-passthrough prepare; then
	:
elif ! grep -q 'tvpath { vdin0([0-9]*) vfm_cap}' $MAP; then
	echo "rm tvpath" > $MAP 2>/dev/null || true
	echo "add tvpath vdin0 vfm_cap" > $MAP
fi

# tvserver starts vdin0 once a client opens the HDMI source
if [ "${VIM4_HDMI_NOTIFY:-0}" = 1 ]; then
	systemd-notify --ready
fi
exec hdmiin-demo </dev/null
