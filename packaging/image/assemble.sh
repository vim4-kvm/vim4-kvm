#!/bin/bash
# Operates on a new regular image file in a Linux ARM64 build VM, never a disk.
set -euo pipefail
[[ $(id -u) == 0 && $(uname -m) == aarch64 ]] || { echo 'Run as root in a Linux ARM64 build VM' >&2; exit 1; }
base=$(realpath "${1:?base image .xz required}")
components=$(realpath "${2:?component package directory required}")
kernels=$(realpath "${3:?kernel package directory required}")
image=$(realpath -m "${4:?new output image path required}")
workspace=$(cd "$(dirname "$0")/../.." && pwd)
[[ -f "$base" && ! -e "$image" && ! -L "$image" ]] || { echo 'Input must be a file; output must not exist' >&2; exit 1; }
for cmd in xz sfdisk growpart losetup mount resize2fs e2fsck python3 chroot; do command -v "$cmd" >/dev/null; done
python3 - "$workspace/packaging/image/base.lock.json" "$base" <<'PY'
import hashlib,json,sys
lock=json.load(open(sys.argv[1]))
with open(sys.argv[2],'rb') as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest()
if actual != lock['sha256']: raise SystemExit('Base image checksum mismatch')
PY
(cd "$components" && sha256sum -c SHA256SUMS)
kernel_name=$(python3 - "$workspace/workspace.toml" "$kernels/kernel-build.json" <<'PY'
import json, sys, tomllib
with open(sys.argv[1], 'rb') as f: lock = tomllib.load(f)
with open(sys.argv[2]) as f: build = json.load(f)
drivers = next(r['revision'] for r in lock['repos'] if r['name'] == 'common_drivers')
if build['kernel'] != lock['kernel']['revision'] or build['drivers'] != drivers:
    raise SystemExit('Kernel build does not match workspace lock')
print(f"linux-image-vim4-kvm_5.15.137+git{build['kernel'][:9]}.{drivers[:9]}-1_arm64.deb")
PY
)
kernel_packages=("$kernels/$kernel_name")
[[ -f ${kernel_packages[0]} ]] || { echo 'Locked kernel package not found' >&2; exit 1; }
(cd "$kernels" && sha256sum -c "$(basename "${kernel_packages[0]}").sha256")
# The official xz expands to disk bytes followed by an OOWOW metadata trailer.
# Remove that trailer before expanding p2; never copy stale size metadata.
(set -C; xz -dc "$base" > "$image")
truncate -s 3338665984 "$image"
python3 - "$image" <<'PY'
import json,subprocess,sys
p=json.loads(subprocess.check_output(['sfdisk','--json',sys.argv[1]]))['partitiontable']
assert p['label']=='dos' and p['sectorsize']==512 and len(p['partitions'])==2, p
b,r=p['partitions']
assert (b['start'],b['size'],r['start'])==(32768,491520,524288), p
PY
truncate -s 8G "$image"
growpart "$image" 2
root_sectors=$(sfdisk --json "$image" | python3 -c 'import json,sys; print(json.load(sys.stdin)["partitiontable"]["partitions"][1]["size"])')
root=$(mktemp -d)
bootloop=''
rootloop=''
cleanup() {
    for path in dev proc boot ''; do
        if mountpoint -q "$root/${path}"; then umount "$root/${path}" || return 1; fi
    done
    [[ -z "$rootloop" ]] || losetup -d "$rootloop"
    [[ -z "$bootloop" ]] || losetup -d "$bootloop"
    rmdir "$root"
}
trap cleanup EXIT
bootloop=$(losetup --find --show --offset 16777216 --sizelimit 251658240 "$image")
rootloop=$(losetup --find --show --offset 268435456 --sizelimit "$((root_sectors * 512))" "$image")
e2fsck -pf "$rootloop" || [[ $? == 1 ]]
resize2fs "$rootloop"
mount "$rootloop" "$root"
mount "$bootloop" "$root/boot"
[[ -L "$root/lib" && $(readlink "$root/lib") == usr/lib ]]
[[ ! -e "$root/usr/sbin/policy-rc.d" ]] || { echo 'Unexpected base policy-rc.d' >&2; exit 1; }
mount -t proc -o ro,nosuid,nodev,noexec proc "$root/proc"
mount -t tmpfs -o nosuid tmpfs "$root/dev"
mknod -m 666 "$root/dev/null" c 1 3
mknod -m 666 "$root/dev/zero" c 1 5
mknod -m 666 "$root/dev/random" c 1 8
mknod -m 666 "$root/dev/urandom" c 1 9
resolv_link=$(readlink "$root/etc/resolv.conf")
rm "$root/etc/resolv.conf"
cp /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 0755 "$root/usr/sbin/policy-rc.d"
mkdir -p "$root/tmp/vim4-packages"
cp "$components"/*.deb "${kernel_packages[0]}" "$root/tmp/vim4-packages/"
cp "$workspace/packaging/image/configure.sh" "$root/tmp/vim4-configure.sh"
chroot "$root" /usr/bin/env VIM4_IMAGE_ASSEMBLY=1 /bin/bash /tmp/vim4-configure.sh
rm "$root/usr/sbin/policy-rc.d" "$root/etc/resolv.conf" "$root/tmp/vim4-configure.sh"
ln -s "$resolv_link" "$root/etc/resolv.conf"
rm -r "$root/tmp/vim4-packages"
mkdir -p "$root/usr/share/vim4-kvm/build"
cp "$components/sources.json" "$components/downloads.lock.json" "$kernels/kernel-build.json" \
    "$workspace/packaging/image/base.lock.json" "$root/usr/share/vim4-kvm/build/"
cp "$workspace/packaging/image/assemble.sh" "$workspace/packaging/image/configure.sh" \
    "$workspace/workspace.toml" "$root/usr/share/vim4-kvm/build/"
git --git-dir="$workspace/.git" rev-parse HEAD > "$root/usr/share/vim4-kvm/build/image-recipe-commit.txt"
cp "$root/usr/share/vim4-kvm/build/image-recipe-commit.txt" "$image.recipe-commit.txt"
chroot "$root" dpkg-query -W > "$image.packages.txt"
cp "$image.packages.txt" "$root/usr/share/vim4-kvm/build/image-packages.txt"
sync
umount "$root/dev" "$root/proc" "$root/boot" "$root"
e2fsck -fn "$bootloop"
e2fsck -fn "$rootloop"
cleanup
trap - EXIT
(cd "$(dirname "$image")" && sha256sum "$(basename "$image")" > "$(basename "$image").sha256")
echo "Assembled (not boot-tested): $image"
