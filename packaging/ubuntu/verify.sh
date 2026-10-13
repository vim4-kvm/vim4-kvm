#!/bin/sh
# Destructive only inside a disposable builder container, never on a board.
set -eu
test -f /.dockerenv
test ! -d /run/systemd/system
cd /packages
sha256sum -c SHA256SUMS
mkdir -p /tmp/package-check/root /tmp/package-check/control
for package in ./*.deb; do
    test "$(dpkg-deb -f "$package" Architecture)" = arm64
    dpkg-deb -x "$package" /tmp/package-check/root
done
test ! -e /tmp/package-check/root/usr/local
python3 /checks/check-audio-startup.py /tmp/package-check/root
dpkg-deb -f ./vim4-kvm-board_*.deb Depends | grep -qw alsa-utils
for binary in /tmp/package-check/root/usr/sbin/usb-pd-init \
    /tmp/package-check/root/opt/vim4-nanokvm/NanoKVM-Server \
    /tmp/package-check/root/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstvfmcap.so \
    /tmp/package-check/root/usr/lib/vim4-kvm/gstreamer-1.0/libgstamlvenc.so; do
    readelf -h "$binary" | grep -q 'Machine:.*AArch64'
    ldd "$binary" > /tmp/package-check/ldd.txt
    if grep -q 'not found' /tmp/package-check/ldd.txt; then
        cat /tmp/package-check/ldd.txt >&2
        exit 1
    fi
done
for file in /tmp/package-check/root/etc/sudoers.d/*; do visudo -cf "$file"; done
test -s /tmp/package-check/root/opt/vim4-nanokvm/web/index.html
useradd --user-group khadas
dpkg-deb -e ./vim4-nanokvm_*.deb /tmp/package-check/control
mkdir -p /usr/share/vim4-nanokvm
cp /tmp/package-check/root/usr/share/vim4-nanokvm/server.yaml /usr/share/vim4-nanokvm/
sh /tmp/package-check/control/postinst configure
test "$(stat -c %U:%a /etc/kvm/server.yaml)" = khadas:600
printf 'existing user settings\n' > /etc/kvm/server.yaml
sh /tmp/package-check/control/postinst configure
test "$(cat /etc/kvm/server.yaml)" = 'existing user settings'
test ! -e /etc/systemd/system/multi-user.target.wants/nanokvm.service
echo 'PASS: checksums, ARM64 ELF, dynamic libraries, sudoers, initial config and upgrade preservation'
