#!/bin/bash
# Invoked only inside the mounted image by assemble.sh.
set -euo pipefail
[[ ${VIM4_IMAGE_ASSEMBLY:-} == 1 ]] || { echo 'Use assemble.sh, not this script directly' >&2; exit 1; }
compgen -G '/tmp/vim4-packages/linux-image-vim4-kvm_*.deb' >/dev/null
[[ -L /lib && $(readlink /lib) == usr/lib ]]
export DEBIAN_FRONTEND=noninteractive
# Runtime dependencies are part of the hash-locked input set. Fail on a missing
# dependency instead of silently selecting a newer version from a live mirror.
mkdir /tmp/vim4-empty-sources
touch /tmp/vim4-empty-sources/list
apt-get --simulate --no-download -o Dir::Etc::sourcelist=/tmp/vim4-empty-sources/list \
    -o Dir::Etc::sourceparts=/tmp/vim4-empty-sources \
    install --no-install-recommends /tmp/vim4-packages/*.deb
dpkg --install /tmp/vim4-packages/*.deb
rm -r /tmp/vim4-empty-sources
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
    vim4-kvm-cpufreq.service vim4-manager.service
app_units=(nanokvm.service vim4-kvm.service one-kvm.service)
[[ ! -f /usr/lib/systemd/system/vim4-pikvm.service ]] || app_units+=(vim4-pikvm.service)
systemctl --root=/ disable "${app_units[@]}"
case ${VIM4_DEFAULT_APP:-nanokvm} in
    nanokvm) app=nanokvm.service;;
    jetkvm) app=vim4-kvm.service;;
    onekvm) app=one-kvm.service;;
    pikvm) app=vim4-pikvm.service;;
    *) echo 'Unknown default app' >&2; exit 1;;
esac
systemctl --root=/ enable "$app"
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
