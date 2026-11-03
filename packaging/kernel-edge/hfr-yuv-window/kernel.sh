#!/bin/bash
set -eu -o pipefail
s=~/src/linux-7.3-hfr-yuv-window
o=~/build/hfr-yuv-window
f=~/build/sdio-formal-52b95c849326/out
test "$(git -C "$s" branch --show-current)" = hfr-yuv-window
test -z "$(git -C "$s" status --porcelain)"
git -C "$s" merge --ff-only "$1"
test "$(git -C "$s" rev-parse HEAD)" = "$1"
cd "$o"
echo "d2fb843dbd5edd6f9d160e1f6876469b7b4bd1897381811cd1562764ce61f8b3  $f/Module.symvers" | sha256sum -c -
cp "$f/.config" .config
kmake() {
    make -C "$s" O="$o" ARCH=arm64 LOCALVERSION=+ KBUILD_BUILD_VERSION=1 \
        KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build -j8 "$@"
}
kmake olddefconfig modules_prepare
cmp "$f/.config" .config
grep -qx '# CONFIG_MODVERSIONS is not set' .config
ln -sfn "$f/vmlinux" vmlinux
# Single-target in-tree modpost does not import Module.symvers. Supply the
# installed providers except those being redefined by this overlay.
awk '$3 !~ /\/(t7-hdmirx|t7-vdin-test|wave5)$/ {print}' "$f/Module.symvers" > baseline.symvers
printf '%s\n' '#!/bin/sh' 'exec ./scripts/mod/modpost -i baseline.symvers "$@"' > formal-modpost
chmod +x formal-modpost
targets=(drivers/media/platform/amlogic/t7-hdmirx/{t7-hdmirx,t7-vdin-test}.ko drivers/media/platform/chips-media/wave5/wave5.ko)
kmake MODPOST="$o/formal-modpost" "${targets[@]}"
for module in "${targets[@]}"; do
    for field in depends vermagic; do
        diff <(modinfo -F "$field" "$f/$module") <(modinfo -F "$field" "$module")
    done
    strip --strip-debug "$module" -o "$2/${module##*/}"
done
