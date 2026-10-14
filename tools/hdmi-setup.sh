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
SDR_WHITE=${HDR_SDR_WHITE:-203}
SDR_PEAK=${HDR_SDR_PEAK:-1000}
case "$SDR_WHITE:$SDR_PEAK" in
	*[!0-9:]*|:*|*:) echo "HDR_SDR_WHITE and HDR_SDR_PEAK must be integers (nits)" >&2; exit 2 ;;
esac
if [ "$SDR_WHITE" -lt 80 ] || [ "$SDR_WHITE" -gt 1000 ] ||
	[ "$SDR_PEAK" -le "$SDR_WHITE" ] || [ "$SDR_PEAK" -gt 10000 ]; then
	echo "Need HDR_SDR_WHITE 80-1000 and HDR_SDR_WHITE < HDR_SDR_PEAK <= 10000" >&2; exit 2
fi
MAP=/sys/class/vfm/map
VDIN=/sys/class/vdin/vdin0/attr
OOTF=/sys/module/aml_media/parameters/oo_y_lut_hdr_sdr
OETF=/sys/module/aml_media/parameters/oe_y_lut_sdr

# HDR10 -> SDR tables for the VDIN0 HDR core (read when vdin0 starts), sampled
# at the HDR2 x positions (linear, 32-bit full scale). Prints two lines:
#   gain: input full scale is 10000 nits, 64 keeps the linear level and output
#         full scale is SDR white. Levels up to 95% of HDR_SDR_WHITE nits (the
#         host's SDR white; BT.2408 uses 203, macOS HDR measured 199) stay
#         linear; an extended Reinhard shoulder rolls the rest into the top 5%
#         so highlights keep gradation up to HDR_SDR_PEAK nits, then clip.
#   oetf: sRGB, which hosts use to decode SDR UI under HDR (macOS fits sRGB,
#         not the vendor gamma 2.2). This table is shared with the VPP/OSD
#         HDR -> SDR paths, so a future HDMI output would use it too.
hdr_sdr_tables() {
	awk -v white="$1" -v peak="$2" 'BEGIN {
		n = 0; x[n++] = 0
		for (i = 1; i < 8; i++) x[n++] = 2 ^ (i + 3)
		for (j = 11; j < 20; j++) for (i = 0; i < 4; i++) x[n++] = 2 ^ (j - 2) * i + 2 ^ j
		for (j = 20; j < 31; j++) for (i = 0; i < 8; i++) x[n++] = 2 ^ (j - 3) * i + 2 ^ j
		for (i = 0; i < 16; i++) x[n++] = 2 ^ 27 * i + 2 ^ 31
		x[n++] = 2 ^ 32 - 1
		knee = 0.95
		top = (peak / white - knee) / (1 - knee)
		for (i = 0; i < n; i++) {
			r = x[i] / 2 ^ 32 * 10000 / white
			t = (r - knee) / (1 - knee)
			if (t > top) t = top
			out = r <= knee ? r : knee + (1 - knee) * t * (1 + t / (top * top)) / (1 + t)
			g = r > 0 ? 64 * out / r * 10000 / white : 64 * 10000 / white
			printf "%s%d", (i ? "," : ""), g + 0.5
		}
		print ""
		for (i = 0; i < n; i++) {
			l = x[i] / 2 ^ 32
			v = l <= 0.0031308 ? 12.92 * l : 1.055 * exp(log(l) / 2.4) - 0.055
			printf "%s%d", (i ? "," : ""), 4095 * v + 0.5
		}
		print ""
	}'
}

modprobe vfm_cap
if [ -w "$OOTF" ] && [ -w "$OETF" ]; then
	hdr_sdr_tables "$SDR_WHITE" "$SDR_PEAK" | {
		read -r gain
		read -r oetf
		echo "$gain" > "$OOTF"
		echo "$oetf" > "$OETF"
	}
else
	echo "HDR to SDR tables not writable; keeping vendor curves" >&2
fi

# tvserver reloads its vendor EDID set at boot; reapply the EDID selected in
# NanoKVM (if any) before the host reads it. A failure keeps the vendor EDID.
if [ -x /usr/libexec/vim4-edid ]; then
	/usr/libexec/vim4-edid restore || echo "EDID restore failed; keeping vendor EDID" >&2
fi

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
