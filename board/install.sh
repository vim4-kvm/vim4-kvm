#!/bin/sh
# Install the board-side KVM setup. Run as root from this directory.
set -eu
cd "$(dirname "$0")"
for tool in mcopy mdir mkfs.vfat fsck.vfat; do
    command -v "$tool" >/dev/null || { echo 'Install mtools and dosfstools before installing board services' >&2; exit 1; }
done
install -D -m 0644 vim4media.py /usr/lib/vim4-kvm/python/vim4media.py
pd_binary=$(mktemp)
trap 'rm -f "$pd_binary"' EXIT HUP INT TERM
cc -O2 -Wall -Wextra -Werror ../tools/usb-pd-init.c -o "$pd_binary"
install -m 0755 "$pd_binary" /usr/local/sbin/usb-pd-init
install -m 0755 ../tools/hdmi-setup.sh /usr/local/sbin/hdmi-setup.sh
install -m 0755 ../tools/hdr-curve.sh /usr/local/sbin/vim4-hdr-curve
install -m 0755 ../tools/kvm-gadget.sh /usr/local/sbin/kvm-gadget.sh
install -m 0644 99-vfm-cap.rules /etc/udev/rules.d/99-vfm-cap.rules
install -m 0644 90-vim4-encoder.conf /etc/modprobe.d/90-vim4-encoder.conf
install -m 0644 vim4-kvm-hdmi.service vim4-kvm-gadget.service vim4-kvm-pd.service /etc/systemd/system/
udevadm control --reload
udevadm trigger --subsystem-match=video4linux
systemctl daemon-reload
systemctl disable usb-gadget-khadas.service 2>/dev/null || true
systemctl enable vim4-kvm-hdmi.service vim4-kvm-gadget.service vim4-kvm-pd.service
systemctl restart vim4-kvm-hdmi.service vim4-kvm-gadget.service
# Only initiate the handoff on boot, not during an install on a live contract.
