#!/bin/bash
# Invoked only inside the mounted image by assemble.sh.
set -euo pipefail
[[ ${VIM4_IMAGE_ASSEMBLY:-} == 1 ]] || { echo 'Use assemble.sh, not this script directly' >&2; exit 1; }
compgen -G '/tmp/vim4-packages/linux-image-vim4-kvm_*.deb' >/dev/null
[[ -L /lib && $(readlink /lib) == usr/lib ]]
export DEBIAN_FRONTEND=noninteractive
printf 'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261012T000000Z %s main universe\n' noble noble-updates noble-security > /tmp/vim4-build.sources.list
apt_options=(-o Dir::Etc::sourcelist=/tmp/vim4-build.sources.list -o Dir::Etc::sourceparts=-)
apt-get "${apt_options[@]}" update
apt-get "${apt_options[@]}" install -y --no-install-recommends /tmp/vim4-packages/*.deb
rm /tmp/vim4-build.sources.list
release=5.15.137-vim4kvm
stock=5.15.137
cp -a /boot/dtb-$stock/amlogic/kvim4*.dtb.overlay* /boot/dtb-$release/amlogic/
update-initramfs -c -k "$release"
ln -sf vmlinuz-$release /boot/Image
ln -sfn dtb-$release /boot/dtb
ln -sf initrd.img-$release /boot/initrd.img
cat > /boot/extlinux/extlinux.conf <<'EOF'
menu background /splash.bmp
LABEL Default
  LINUX /Image
  INITRD /initrd.img
  FDTDIR /dtb
  APPEND ${rootdev} ${bootargs} ${consoles} ${partitiontype} fan=${fan_mode} ${boot_user_args}

LABEL Stock
  LINUX /vmlinuz-5.15.137
  INITRD /initrd.img-5.15.137
  FDTDIR /dtb-5.15.137
  APPEND ${rootdev} ${bootargs} ${consoles} ${partitiontype} fan=${fan_mode} ${boot_user_args}

timeout 5
default Default
EOF
/usr/sbin/vim4-rootfs-policy /
systemctl --root=/ disable usb-gadget-khadas.service audioserver.service
systemctl --root=/ enable vim4-kvm-gadget.service vim4-kvm-pd.service vim4-kvm-hdmi.service \
    vim4-kvm-cpufreq.service nanokvm.service vim4-manager.service
# SSH host identity must be generated per installation, never copied into images.
rm -f /etc/ssh/ssh_host_*
cat > /usr/lib/systemd/system/vim4-kvm-firstboot.service <<'EOF'
[Unit]
Description=Generate this installation's SSH host keys
Before=ssh.service
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
RequiredBy=ssh.service
EOF
systemctl --root=/ enable vim4-kvm-firstboot.service
truncate -s 0 /etc/machine-id
apt-get clean
rm -rf /var/lib/apt/lists/*
[[ -L /lib && -s /boot/initrd.img-$release && -s /boot/initrd.img-$stock ]]
test -f /usr/lib/modules/$release/extra/amlogic/vfm_cap.ko
dpkg --audit
