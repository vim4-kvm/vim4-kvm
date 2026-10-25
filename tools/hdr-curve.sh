#!/bin/sh
# HDR10 -> SDR mapping for the VDIN0 HDR core.
#
# Usage: vim4-hdr-curve tables WHITE PEAK   print the legacy gain and sRGB tables
#        vim4-hdr-curve tables-edge WHITE PEAK  print edge highlight-preserving tables
#        vim4-hdr-curve apply WHITE PEAK    write them and reload a running vdin0
# Exit 2: invalid arguments; 3: this kernel has no writable tables.
#
# WHITE is the host's SDR white in nits (BT.2408 uses 203, macOS HDR measured
# 199; at least 160, see the gain table below) and PEAK the brightest highlight
# that keeps gradation. apply runs as root
# (hdmi-setup.sh before vdin0 starts, vim4-manager-helper for live previews).
set -eu

OOTF=/sys/module/aml_media/parameters/oo_y_lut_hdr_sdr
OETF=/sys/module/aml_media/parameters/oe_y_lut_sdr
VDIN=/sys/class/vdin/vdin0/attr
CAPTURE_GAIN=/sys/module/aml_media/parameters/vdin_oo_y_lut_hdr_sdr
SECONDARY=/sys/class/vdin/vdin1/attr
NATIVE_HDR=/sys/module/aml_media/parameters/vdin0_native_hdr
EDGE_CURVE=/sys/bus/platform/devices/ff000000.video-capture/hdr_curve

usage() {
	echo "Usage: $0 tables|tables-edge|apply WHITE PEAK (WHITE 160-1000 nits, WHITE < PEAK <= 10000)" >&2
	exit 2
}

[ "$#" = 3 ] || usage
ACTION=$1
WHITE=$2
PEAK=$3
case "$ACTION:$WHITE:$PEAK" in
	tables:*|tables-edge:*|apply:*) ;;
	*) usage ;;
esac
for value in "$WHITE" "$PEAK"; do
	case "$value" in
		''|*[!0-9]*|0*) usage ;;
	esac
done
if [ "${#WHITE}" -gt 5 ] || [ "${#PEAK}" -gt 5 ] ||
	[ "$WHITE" -lt 160 ] || [ "$WHITE" -gt 1000 ] ||
	[ "$PEAK" -le "$WHITE" ] || [ "$PEAK" -gt 10000 ]; then
	usage
fi

# Both tables are sampled at the HDR2 x positions (linear, 32-bit full scale).
#   gain: input full scale is 10000 nits, 64 keeps the linear level and output
#         full scale is SDR white. The 12-bit gain register caps the gain at
#         4095, i.e. WHITE >= 157 nits; lower whites wrap and darken the
#         picture, hence the 160 minimum. Legacy keeps 95% of WHITE linear,
#         then uses an extended Reinhard shoulder. Edge preserves sRGB codes
#         through 90%, then reserves the remaining codes for a log shoulder
#         up to PEAK. This retains highlight distinctions in 8-bit output.
#   oetf: sRGB, which hosts use to decode SDR UI under HDR (macOS fits sRGB,
#         not the vendor gamma 2.2). This table is shared with the VPP/OSD
#         HDR -> SDR paths, so a future HDMI output would use it too.
tables() {
	awk -v white="$WHITE" -v peak="$PEAK" -v edge="${1:-0}" '
	function decode(v) {
		return v <= 0.04045 ? v / 12.92 : exp(2.4 * log((v + 0.055) / 1.055))
	}
	BEGIN {
		n = 0; x[n++] = 0
		for (i = 1; i < 8; i++) x[n++] = 2 ^ (i + 3)
		for (j = 11; j < 20; j++) for (i = 0; i < 4; i++) x[n++] = 2 ^ (j - 2) * i + 2 ^ j
		for (j = 20; j < 31; j++) for (i = 0; i < 8; i++) x[n++] = 2 ^ (j - 3) * i + 2 ^ j
		for (i = 0; i < 16; i++) x[n++] = 2 ^ 27 * i + 2 ^ 31
		x[n++] = 2 ^ 32 - 1
		knee = 0.95
		top = (peak / white - knee) / (1 - knee)
		# The legacy 5% linear-light shoulder collapses bright HDR levels to
		# one 8-bit white code. On edge keep sRGB codes <= 90% unchanged,
		# then use a logarithmic shoulder up to PEAK. Match its derivative
		# at the join so gradients do not acquire a visible corner.
		if (edge) {
			encoded_knee = 0.9
			linear_knee = decode(encoded_knee)
			span = peak / white - linear_knee
			slope = 1.055 / (2.4 * exp(1.4 * log((encoded_knee + 0.055) / 1.055)))
			lo = 0; hi = 1
			while (0.1 * hi / log(1 + hi * span) < slope) hi *= 2
			for (j = 0; j < 64; j++) {
				a = (lo + hi) / 2
				if (0.1 * a / log(1 + a * span) < slope) lo = a
				else hi = a
			}
			shoulder = (lo + hi) / 2
			normalizer = log(1 + shoulder * span)
		}
		for (i = 0; i < n; i++) {
			r = x[i] / 2 ^ 32 * 10000 / white
			t = (r - knee) / (1 - knee)
			if (t > top) t = top
			out = r <= knee ? r : knee + (1 - knee) * t * (1 + t / (top * top)) / (1 + t)
			if (edge && r > linear_knee) {
				level = r > peak / white ? peak / white : r
				encoded = encoded_knee + 0.1 * log(1 + shoulder * (level - linear_knee)) / normalizer
				out = decode(encoded)
			} else if (edge) out = r
			g = r > 0 ? 64 * out / r * 10000 / white : 64 * 10000 / white
			printf "%s%d", (i ? "," : ""), (g > 4095 ? 4095 : g + 0.5)
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

if [ "$ACTION" = tables ] || [ "$ACTION" = tables-edge ]; then
	if [ "$ACTION" = tables-edge ]; then tables 1; else tables; fi
	exit 0
fi

if [ -w "$EDGE_CURVE" ]; then
	# The edge driver validates and queues both tables atomically. Its capture
	# IRQ loads them only with the MIF gated at a completed frame boundary.
	curve=$(tables 1)
	printf '%s\n' "$curve" > "$EDGE_CURVE"
	exit 0
fi
if [ ! -w "$OOTF" ] || [ ! -w "$OETF" ]; then
	echo "HDR to SDR tables not writable; keeping vendor curves" >&2
	exit 3
fi
tables | {
	read -r gain
	read -r oetf
	echo "$gain" > "$OOTF"
	echo "$oetf" > "$OETF"
	if [ -w "$CAPTURE_GAIN" ]; then
		echo "$gain" > "$CAPTURE_GAIN"
	fi
}
# The capture ISR applies the request at a frame boundary. Without an active
# input it stays pending until capture starts; a failed write is a real error.
echo reload_hdr > "$VDIN"
if [ -r "$NATIVE_HDR" ] && [ "$(cat "$NATIVE_HDR")" = Y ] && [ -w "$SECONDARY" ]; then
	echo reload_hdr > "$SECONDARY"
fi
