#!/bin/sh
# Install a vim4-kvm kernel tarball on the board and make it the default boot entry.
# The stock kernel stays available as the "Stock" extlinux entry.
#
# Usage (on the board): sudo sh kernel-install.sh vim4kvm-<release>.tgz
set -eu

TGZ=$1
R=$(tar tzf "$TGZ" | sed -n 's#^lib/modules/\([^/]*\)/$#\1#p' | head -1)
STOCK=5.15.137
[ -n "$R" ] || { echo "no lib/modules/<release>/ in $TGZ" >&2; exit 1; }
echo "release: $R"
case "$R" in
    7.*) echo 'Use the kernel-edge board window and register-runtime.py for /boot/edge; this installer owns the vendor boot layout' >&2; exit 1 ;;
esac

# /lib is a symlink to usr/lib on Ubuntu 24.04; without
# --keep-directory-symlink tar replaces it and breaks the dynamic loader.
tar xzf "$TGZ" -C / --no-same-owner --keep-directory-symlink
[ -L /lib ] || { echo "/lib is no longer a symlink!" >&2; exit 1; }

cp -a /boot/dtb-$STOCK/amlogic/kvim4*.dtb.overlay* /boot/dtb-$R/amlogic/

[ -e /boot/extlinux/extlinux.conf.stock ] ||
	cp /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.stock
APPEND='${rootdev} ${bootargs} ${consoles} ${partitiontype} fan=${fan_mode} ${boot_user_args}'
cat > /boot/extlinux/extlinux.conf <<EOF
menu background /splash.bmp
LABEL Default
  LINUX /Image
  INITRD /initrd.img
  FDTDIR /dtb
  APPEND $APPEND

LABEL Stock
  LINUX /vmlinuz-$STOCK
  INITRD /initrd.img-$STOCK
  FDTDIR /dtb-$STOCK
  APPEND $APPEND

timeout 5
default Default
EOF

# the 99-uboot post-update hook repoints /boot/initrd.img
update-initramfs -c -k "$R" || update-initramfs -u -k "$R"
ln -sf vmlinuz-$R /boot/Image
ln -sfn dtb-$R /boot/dtb
sync
ls -l /boot/Image /boot/initrd.img /boot/dtb
