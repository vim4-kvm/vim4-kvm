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
case "$LOW_LATENCY" in
	0|1) ;;
	*) echo "HDMI_LOW_LATENCY must be 0 or 1" >&2; exit 2 ;;
esac
case "$W:$H" in
	3840:2160|1920:1080|1280:720) ;;
	*) echo "Unsupported capture size: $W x $H (use 3840x2160, 1920x1080 or 1280x720)" >&2; exit 2 ;;
esac
MAP=/sys/class/vfm/map
VDIN=/sys/class/vdin/vdin0/attr

modprobe vfm_cap

pkill -x hdmiin-demo 2>/dev/null && sleep 2 || true

# 8-bit only: the 4K 10-bit default is Amlogic packed 422 (AMLY)
echo "color_depth_support 0x1" > $VDIN
# linear little-endian writes, as the CPU/encoder read them
echo "no_swap_en 1" > $VDIN
# hw scaler + NV21 (TVIN_NV21 = 8)
echo "conversion $W $H 8" > $VDIN

# BIT0 | BIT1 selects completed-frame game mode 1. With RDMA, the normal
# path otherwise retains the finished frame until the following interrupt.
# Never enable BIT2: its same-buffer read/write path is unsafe for DMA-buf
# consumers without additional synchronization. Zero restores vendor policy.
if [ "$LOW_LATENCY" = 1 ]; then
	echo "game_mode 3" > $VDIN
else
	echo "game_mode 0" > $VDIN
fi

if ! grep -q 'tvpath { vdin0([0-9]*) vfm_cap}' $MAP; then
	echo "rm tvpath" > $MAP 2>/dev/null || true
	echo "add tvpath vdin0 vfm_cap" > $MAP
fi

# tvserver starts vdin0 once a client opens the HDMI source
exec hdmiin-demo </dev/null
