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
    /tmp/package-check/root/opt/vim4-jetkvm/jetkvm \
    /tmp/package-check/root/opt/vim4-onekvm/one-kvm \
    /tmp/package-check/root/opt/vim4-onekvm/lib/libgst-aml-dma-allocator.so \
    /tmp/package-check/root/opt/vim4-manager/vim4-manager \
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
test "$(cat /tmp/package-check/root/opt/vim4-nanokvm/version)" = "$(dpkg-deb -f ./vim4-nanokvm_*.deb Version)"
test -x /tmp/package-check/root/usr/libexec/vim4-picoclaw
test ! -e /tmp/package-check/root/opt/vim4-nanokvm/assistant
test -d /tmp/package-check/root/opt/vim4-nanokvm/picoclaw/skills/kvm-control
useradd --user-group khadas
dpkg-deb -e ./vim4-nanokvm_*.deb /tmp/package-check/control
mkdir -p /usr/share/vim4-nanokvm
cp /tmp/package-check/root/usr/share/vim4-nanokvm/server.yaml /usr/share/vim4-nanokvm/
mkdir -p /usr/libexec
cp -a /tmp/package-check/root/usr/libexec/. /usr/libexec/
cp -a /tmp/package-check/root/etc/sudoers.d/. /etc/sudoers.d/
sh /tmp/package-check/control/postinst configure
test "$(stat -c %U:%a /etc/kvm/server.yaml)" = khadas:600
test "$(stat -c %U:%a /var/lib/vim4-kvm/picoclaw)" = khadas:700
printf 'existing user settings\n' > /etc/kvm/server.yaml
# Simulate an installed assistant with a live worker and private runtime data.
# The upgrade must retire it without touching the surviving PicoClaw state.
mkdir -p /opt/vim4-nanokvm/assistant /var/lib/vim4-kvm/assistant/bin
ln -s /usr/bin/python3 /var/lib/vim4-kvm/assistant/bin/python
printf 'import pathlib,time; pathlib.Path("/tmp/assistant-ready").touch(); time.sleep(120)\n' > /opt/vim4-nanokvm/assistant/cua_webapp.py
printf 'legacy settings\n' > /var/lib/vim4-kvm/assistant/settings
printf 'PicoClaw settings\n' > /var/lib/vim4-kvm/picoclaw/keep
/var/lib/vim4-kvm/assistant/bin/python /opt/vim4-nanokvm/assistant/cua_webapp.py --auth &
assistant_pid=$!
remaining=50
while [ ! -f /tmp/assistant-ready ]; do
    kill -0 "$assistant_pid"
    test "$remaining" -gt 0
    sleep 0.1
    remaining=$((remaining - 1))
done
sh /tmp/package-check/control/postinst configure
if kill -0 "$assistant_pid" 2>/dev/null; then
    echo 'Retired assistant is still running' >&2
    exit 1
fi
wait "$assistant_pid" 2>/dev/null || true
test ! -e /opt/vim4-nanokvm/assistant
test ! -e /var/lib/vim4-kvm/assistant
test "$(cat /var/lib/vim4-kvm/picoclaw/keep)" = 'PicoClaw settings'
test "$(cat /etc/kvm/server.yaml)" = 'existing user settings'
test ! -e /etc/systemd/system/multi-user.target.wants/nanokvm.service
# A crash previously left a conffile empty. Configuration must not report
# success merely because visudo accepts an empty sudoers include.
truncate -s 0 /etc/sudoers.d/vim4-media
if sh /tmp/package-check/control/postinst configure; then
    echo 'Empty sudoers file incorrectly accepted' >&2
    exit 1
fi
cp -a /tmp/package-check/root/etc/sudoers.d/vim4-media /etc/sudoers.d/
# Installing the JetKVM package must not change which application boots.
dpkg-deb -e ./vim4-jetkvm_*.deb /tmp/package-check/jetkvm-control
sh /tmp/package-check/jetkvm-control/postinst configure
test ! -e /etc/systemd/system/multi-user.target.wants/vim4-kvm.service
truncate -s 0 /etc/sudoers.d/vim4-jetkvm
if sh /tmp/package-check/jetkvm-control/postinst configure; then
    echo 'Empty JetKVM sudoers file incorrectly accepted' >&2
    exit 1
fi
cp -a /tmp/package-check/root/etc/sudoers.d/vim4-jetkvm /etc/sudoers.d/
grep -qx 'Conflicts=nanokvm.service' /tmp/package-check/root/usr/lib/systemd/system/vim4-kvm.service
dpkg-deb -e ./vim4-onekvm_*.deb /tmp/package-check/onekvm-control
mkdir -p /opt/vim4-onekvm/lib
cp /tmp/package-check/root/opt/vim4-onekvm/lib/libgst-aml-dma-allocator.so /opt/vim4-onekvm/lib/
cp -a /tmp/package-check/root/opt/vim4-onekvm/bin /opt/vim4-onekvm/
for binary in /opt/vim4-onekvm/bin/*; do
    readelf -h "$binary" | grep -q 'Machine:.*AArch64'
done
mkdir -p /usr/share/vim4-onekvm
cp -a /tmp/package-check/root/usr/share/vim4-onekvm/ventoy /usr/share/vim4-onekvm/
sh /tmp/package-check/onekvm-control/postinst configure
getcap /opt/vim4-onekvm/bin/easytier-core | grep -q 'cap_net_admin=ep'
test -x /usr/bin/ttyd
for resource in boot.img core.img ventoy.disk.img; do
    mv "/usr/share/vim4-onekvm/ventoy/$resource" /tmp/ventoy-resource
    if sh /tmp/package-check/onekvm-control/postinst configure; then
        echo "Missing Ventoy resource incorrectly accepted: $resource" >&2
        exit 1
    fi
    mv /tmp/ventoy-resource "/usr/share/vim4-onekvm/ventoy/$resource"
done
test ! -e /etc/systemd/system/multi-user.target.wants/one-kvm.service
truncate -s 0 /etc/sudoers.d/vim4-onekvm
if sh /tmp/package-check/onekvm-control/postinst configure; then
    echo 'Empty One-KVM sudoers file incorrectly accepted' >&2
    exit 1
fi
cp -a /tmp/package-check/root/etc/sudoers.d/vim4-onekvm /etc/sudoers.d/
grep -qx 'Conflicts=nanokvm.service vim4-kvm.service' /tmp/package-check/root/usr/lib/systemd/system/one-kvm.service
dpkg-deb -e ./vim4-manager_*.deb /tmp/package-check/manager-control
sh /tmp/package-check/manager-control/postinst configure
truncate -s 0 /etc/sudoers.d/vim4-manager-helper
if sh /tmp/package-check/manager-control/postinst configure; then
    echo 'Empty manager sudoers file incorrectly accepted' >&2
    exit 1
fi
echo 'PASS: checksums, ARM64 ELF, libraries, sudoers, config preservation, damaged-file rejection'
python3 /checks/check-onekvm-update.py
