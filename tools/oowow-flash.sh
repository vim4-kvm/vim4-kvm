#!/usr/bin/env bash
# Flash an OS image into VIM4 eMMC through the OOWOW serial console.
#
# The board must already be booted into OOWOW (hold FUNCTION, tap RESET, release FUNCTION)
# with Ethernet connected. Everything runs on the board; the Mac only drives the serial shell.
#
# Usage: tools/oowow-flash.sh --yes [IMAGE_NAME_OR_URL]
#
# Why not the official `curl 127.0.0.1/shell/write | sh -s - IMAGE`:
#   - OOWOW lacks the `file` command, so the script misdetects the format and wipes the GPT.
#   - Piping a download straight into /api/disk/write stalls (chunked upload never reaches pixz).
# So: download into /tmp (tmpfs, RAM), `xz -t`, upload with Content-Length, then verify by md5.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
RUN="$DIR/uart-run.py"
DEFAULT_IMAGE=vim4-ubuntu-24.04-server-linux-5.15-fenix-1.7.5-250925.img.xz
BASE=https://dl.khadas.com/.images/vim4

[ "${1:-}" = "--yes" ] || { echo "This ERASES the VIM4 eMMC. Re-run with --yes [IMAGE]" >&2; exit 1; }
IMAGE=${2:-$DEFAULT_IMAGE}
case $IMAGE in http*) URL=$IMAGE ;; *) URL=$BASE/$IMAGE ;; esac

run() { "$RUN" -t "${2:-20}" "$1"; }
wait_for() { # wait_for <remote file> <label>
  while ! out=$(run "cat $1 2>/dev/null; $3" 15) || ! grep -q EXIT <<<"$out"; do
    echo "  [$2] $(tr '\n' ' ' <<<"$out")"; sleep 15
  done
  grep -q 'EXIT=0' <<<"$out" || { echo "[e] $2 failed: $out" >&2; exit 1; }
}

echo "[i] checking OOWOW"
run '[ -d /www/x/api/disk ] && echo OOWOW_OK' | grep -q OOWOW_OK || { echo "[e] board is not in OOWOW" >&2; exit 1; }

echo "[i] downloading $URL"
run "rm -f /tmp/img.xz /tmp/dl.done /tmp/wr.*; (curl -sSL -o /tmp/img.xz '$URL'; echo EXIT=\$? > /tmp/dl.done) >/tmp/dl.err 2>&1 &"
wait_for /tmp/dl.done download 'ls -l /tmp/img.xz | awk "{print \$5}"'

echo "[i] testing archive"
run 'xz -t /tmp/img.xz && echo XZ_OK' 300 | grep -q XZ_OK || { echo "[e] xz test failed" >&2; exit 1; }

echo "[i] writing eMMC"
run '(curl -sS -T /tmp/img.xz -o /tmp/wr.log 127.0.0.1/api/disk/write/mmc.xz; echo EXIT=$? > /tmp/wr.done) >/tmp/wr.err 2>&1 &'
wait_for /tmp/wr.done write 'awk "/mmcblk0 /{print \$10*512/1048576 \" MB written\"}" /proc/diskstats'

echo "[i] verifying (md5 of image vs eMMC)"
run 'sync; S=$(xz -dc /tmp/img.xz | wc -c); A=$(xz -dc /tmp/img.xz | md5sum | cut -d" " -f1); B=$(head -c $S /dev/mmcblk0 | md5sum | cut -d" " -f1); echo "$A $B"; [ "$A" = "$B" ] && echo VERIFY_OK' 600 \
  | tee /dev/stderr | grep -q VERIFY_OK || { echo "[e] verify failed" >&2; exit 1; }

echo "[i] done. Reboot into the new system with: tools/uart-log.py --send 'sync; reboot'"
