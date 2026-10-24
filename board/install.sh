#!/bin/sh
# Install the board-side KVM setup. Run as root from this directory.
set -eu
cd "$(dirname "$0")"
for tool in mcopy mdir mkfs.vfat fsck.vfat; do
    command -v "$tool" >/dev/null || { echo 'Install mtools and dosfstools before installing board services' >&2; exit 1; }
done
sh ./install-logging.sh
install -D -m 0644 60-vim4-watchdog.conf /usr/lib/systemd/system.conf.d/60-vim4-watchdog.conf
install -D -m 0644 60-vim4-panic.conf /usr/lib/sysctl.d/60-vim4-panic.conf
install -D -m 0644 vim4media.py /usr/lib/vim4-kvm/python/vim4media.py
install -D -m 0644 vim4video.py /usr/lib/vim4-kvm/python/vim4video.py
install -D -m 0644 vim4boot.py /usr/lib/vim4-kvm/python/vim4boot.py
install -D -m 0644 edid/1080p60-sdr8.bin /usr/share/vim4-kvm/edid/1080p60-sdr8.bin
install -D -m 0755 vim4-board-runtime /usr/libexec/vim4-board-runtime
install -D -m 0755 vim4-wave5-monitor.py /usr/libexec/vim4-wave5-monitor
if [ ! -e /etc/default/vim4-wave5-monitor ]; then
    install -D -m 0644 vim4-wave5-monitor.conf /etc/default/vim4-wave5-monitor
fi
install -D -m 0755 vim4-kvm-run /usr/libexec/vim4-kvm-run
install -D -m 0755 ../packaging/kernel-edge/one-kvm-edge-prepare /usr/libexec/vim4-mainline-prepare
install -D -m 0755 ../packaging/kernel-edge/one-kvm-edge-usb-prepare /usr/libexec/vim4-mainline-gadget-prepare
pd_binary=$(mktemp)
trap 'rm -f "$pd_binary"' EXIT HUP INT TERM
cc -O2 -Wall -Wextra -Werror ../tools/usb-pd-init.c -o "$pd_binary"
install -m 0755 "$pd_binary" /usr/sbin/usb-pd-init
install -D -m 0644 vim4pd.py /usr/lib/vim4-kvm/python/vim4pd.py
install -m 0755 ../tools/hdmi-setup.sh /usr/sbin/hdmi-setup.sh
install -m 0755 ../tools/hdr-curve.sh /usr/sbin/vim4-hdr-curve
install -m 0755 ../tools/kvm-gadget.sh /usr/sbin/kvm-gadget.sh
install -m 0644 99-vfm-cap.rules /etc/udev/rules.d/99-vfm-cap.rules
install -m 0644 90-vim4-encoder.conf /etc/modprobe.d/90-vim4-encoder.conf
install -m 0644 vim4-kvm-hdmi.service vim4-kvm-gadget.service vim4-kvm-pd.service /etc/systemd/system/
install -m 0644 vim4-wave5-monitor.service /etc/systemd/system/
udevadm control --reload
udevadm trigger --subsystem-match=video4linux
systemctl daemon-reload
systemctl disable usb-gadget-khadas.service 2>/dev/null || true
systemctl enable vim4-kvm-hdmi.service vim4-kvm-gadget.service vim4-kvm-pd.service
systemctl enable --now vim4-wave5-monitor.service
systemctl restart vim4-kvm-hdmi.service vim4-kvm-gadget.service
# Only initiate the handoff on boot, not during an install on a live contract.
