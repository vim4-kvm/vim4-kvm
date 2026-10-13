#!/bin/bash
# Read-only structural checks; these cannot establish that a board will boot.
set -euo pipefail
image=$(realpath "${1:?image file required}")
base=$(realpath "${2:?locked base .xz required}")
[[ $(id -u) == 0 && -f "$image" && -f "$base" ]]
read -r root_start root_sectors < <(python3 - "$image" "$base" <<'PY'
import json,lzma,subprocess,sys
with lzma.open(sys.argv[2],'rb') as source: old=source.read(16777216)
with open(sys.argv[1],'rb') as image: new=image.read(16777216)
assert old[:446]==new[:446] and old[510:]==new[510:], 'Bootloader region changed'
p=json.loads(subprocess.check_output(['sfdisk','--json',sys.argv[1]]))['partitiontable']
assert p['label']=='dos' and p['sectorsize']==512 and len(p['partitions'])==2
b,r=p['partitions']
assert (b['start'],b['size'],r['start'])==(32768,491520,524288)
print(r['start'],r['size'])
PY
)
root=$(mktemp -d)
bootloop=''; rootloop=''
cleanup() {
    for path in dev tmp boot ''; do if mountpoint -q "$root/$path"; then umount "$root/$path" || return 1; fi; done
    [[ -z "$rootloop" ]] || losetup -d "$rootloop"
    [[ -z "$bootloop" ]] || losetup -d "$bootloop"
    rmdir "$root"
}
trap cleanup EXIT
bootloop=$(losetup --find --show --read-only --offset 16777216 --sizelimit 251658240 "$image")
rootloop=$(losetup --find --show --read-only --offset "$((root_start * 512))" --sizelimit "$((root_sectors * 512))" "$image")
mount -o ro,noload "$rootloop" "$root"
mount -o ro,noload "$bootloop" "$root/boot"
mount -t tmpfs -o nosuid tmpfs "$root/dev"
mount -t tmpfs -o nosuid,nodev tmpfs "$root/tmp"
mknod -m 666 "$root/dev/null" c 1 3
release=5.15.137-vim4kvm
[[ -L "$root/lib" && $(readlink "$root/lib") == usr/lib ]]
[[ $(readlink "$root/boot/Image") == vmlinuz-$release ]]
[[ $(readlink "$root/boot/dtb") == dtb-$release ]]
[[ $(readlink "$root/boot/initrd.img") == initrd.img-$release ]]
for path in vmlinuz-5.15.137 initrd.img-5.15.137 dtb-5.15.137/amlogic/kvim4n.dtb; do test -s "$root/boot/$path"; done
grep -q '^LABEL Stock' "$root/boot/extlinux/extlinux.conf"
grep -q "UUID=$(blkid -s UUID -o value "$bootloop")" "$root/etc/fstab"
grep -q "UUID=$(blkid -s UUID -o value "$rootloop")" "$root/etc/fstab"
for unit in vim4-kvm-hdmi vim4-kvm-gadget vim4-kvm-pd vim4-kvm-cpufreq vim4-kvm-firstboot nanokvm; do
    systemctl --root="$root" is-enabled "$unit.service"
done
test ! -e "$root/etc/systemd/system/multi-user.target.wants/audioserver.service"
python3 "$(dirname "$0")/../ubuntu/check-audio-startup.py" "$root"
python3 "$root/usr/sbin/vim4-rootfs-policy" --check "$root"
chroot "$root" /usr/bin/amixer --version
test -L "$root/etc/systemd/system/ssh.service.requires/vim4-kvm-firstboot.service"
test ! -e "$root/usr/sbin/policy-rc.d"
test ! -s "$root/etc/machine-id"
test -L "$root/etc/resolv.conf"
if compgen -G "$root/etc/ssh/ssh_host_*" >/dev/null; then echo 'Image contains shared SSH keys' >&2; exit 1; fi
audit=$(chroot "$root" dpkg --audit)
[[ -z "$audit" ]] || { echo "$audit" >&2; exit 1; }
chroot "$root" modprobe -n -v -S "$release" vfm_cap > "$image.module-dependencies.txt"
for binary in /opt/vim4-nanokvm/NanoKVM-Server /usr/lib/vim4-kvm/gstreamer-1.0/libgstamlvenc.so; do
    result=$(chroot "$root" ldd "$binary")
    if grep -q 'not found' <<<"$result"; then echo "$result" >&2; exit 1; fi
done
for file in "$root"/etc/sudoers.d/vim4-*; do chroot "$root" visudo -cf "${file#"$root"}"; done
chroot "$root" lsinitramfs "/boot/initrd.img-$release" > "$image.initramfs-list.txt"
grep -q "modules/$release" "$image.initramfs-list.txt"
printf 'PASS: bootloader bytes, layout, boot links, stock fallback, UUIDs, modules, services, identity, libraries, sudoers, initramfs\n'
