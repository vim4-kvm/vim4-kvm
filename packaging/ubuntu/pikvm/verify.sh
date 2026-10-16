#!/bin/sh
# Only run in a disposable builder container, never on the host or board.
set -eu
test -f /.dockerenv
test ! -d /run/systemd/system
test "$(dpkg --print-architecture)" = arm64
cd /packages
sha256sum -c SHA256SUMS
getent passwd khadas >/dev/null || useradd -m khadas
for file in ./*.deb; do dpkg-deb -x "$file" /; done
package=$(find . -maxdepth 1 -name 'vim4-pikvm_*.deb')
dpkg-deb -f "$package" Depends | grep -qw vim4-media-api-1
mkdir /tmp/pikvm-control
dpkg-deb -e "$package" /tmp/pikvm-control
sh /tmp/pikvm-control/postinst configure
sha256sum /etc/kvmd/htpasswd > /tmp/credentials.sha256
sh /tmp/pikvm-control/postinst configure
sha256sum -c /tmp/credentials.sha256
for binary in /usr/bin/janus /usr/bin/ustreamer /usr/lib/ustreamer/janus/*.so /opt/vim4-pikvm/bin/nginx; do
    file "$binary" | grep 'ARM aarch64'
    if ldd "$binary" | grep 'not found'; then exit 1; fi
done
export KVMD_PLATFORM=vim4 PATH=/opt/vim4-pikvm/python/bin:$PATH
kvmd -m > /tmp/kvmd-config.yaml
python3.14 -c 'import ustreamer; from kvmd.apps.kvmd import main; from kvmd.apps.media import main'
mkdir -p /run/kvmd
/opt/vim4-pikvm/bin/nginx -t -c /etc/kvmd/nginx/vim4.conf
/usr/bin/python3 /checks/pikvm/check-janus.py
test -s /usr/share/kvmd/web/kvm/index.html
test ! -e /etc/systemd/system/multi-user.target.wants/vim4-pikvm.service
python3 /checks/check-feeds.py /packages
