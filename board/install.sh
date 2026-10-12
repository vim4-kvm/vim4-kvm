#!/bin/sh
# Install the board-side KVM setup. Run as root from this directory.
set -eu
cd "$(dirname "$0")"
install -m 0755 ../tools/hdmi-setup.sh /usr/local/sbin/hdmi-setup.sh
install -m 0755 ../tools/kvm-gadget.sh /usr/local/sbin/kvm-gadget.sh
install -m 0644 99-vfm-cap.rules /etc/udev/rules.d/99-vfm-cap.rules
install -m 0644 vim4-kvm-hdmi.service vim4-kvm-gadget.service /etc/systemd/system/
udevadm control --reload
udevadm trigger --subsystem-match=video4linux
systemctl daemon-reload
systemctl disable usb-gadget-khadas.service 2>/dev/null || true
systemctl enable vim4-kvm-hdmi.service vim4-kvm-gadget.service
systemctl restart vim4-kvm-hdmi.service vim4-kvm-gadget.service
