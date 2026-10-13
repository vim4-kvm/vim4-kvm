#!/bin/bash
# Native Linux ARM64 kernel build and package; never installs on the host.
set -euo pipefail
source_dir=$(realpath "${1:?kernel source directory required}")
output=$(realpath -m "${2:?output directory required}")
workspace=$(cd "$(dirname "$0")/../.." && pwd)
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'Requires Linux ARM64' >&2; exit 1; }
python3 - "$workspace" "$source_dir" <<'PY'
import hashlib, pathlib, subprocess, sys, tomllib
workspace, source = map(pathlib.Path, sys.argv[1:])
lock = tomllib.loads((workspace/'workspace.toml').read_text())
drivers = next(r for r in lock['repos'] if r['name']=='common_drivers')
for path, revision in [(source, lock['kernel']['revision']), (source/'common_drivers', drivers['revision'])]:
    actual = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    dirty = subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip()
    if actual != revision or dirty: raise SystemExit(f'Source mismatch or dirty tree: {path}')
if (source/'.config').read_bytes() != (workspace/'packaging/kernel/vim4.config').read_bytes():
    raise SystemExit('Kernel .config differs from packaging/kernel/vim4.config; review it before building')
PY
mkdir -p "$output"
cd "$source_dir"
kernel_commit=$(git rev-parse HEAD)
driver_commit=$(git -C common_drivers rev-parse HEAD)
version="5.15.137+git${kernel_commit:0:9}.${driver_commit:0:9}-1"
package="$output/linux-image-vim4-kvm_${version}_arm64.deb"
[[ ! -e "$package" ]] || { echo "Already exists: $package" >&2; exit 1; }
export SOURCE_DATE_EPOCH=$(git show -s --format=%ct HEAD)
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH")
make_args=(ARCH=arm64 CC=gcc-12 KBUILD_BUILD_VERSION=1 KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build)
touch .scmversion
make "${make_args[@]}" olddefconfig
make "${make_args[@]}" -j"${JOBS:-10}" Image dtbs modules
make "${make_args[@]}" M="$source_dir/common_drivers/drivers/media/vfm_cap" modules
release=$(make -s "${make_args[@]}" kernelrelease)
[[ "$release" == 5.15.137-vim4kvm ]] || { echo "Unexpected release $release" >&2; exit 1; }
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
make "${make_args[@]}" modules_install INSTALL_MOD_PATH="$stage" INSTALL_MOD_STRIP=1
mkdir -p "$stage/usr/lib"
mv "$stage/lib/modules" "$stage/usr/lib/"
rmdir "$stage/lib"
modules="$stage/usr/lib/modules/$release"
rm -f "$modules/build" "$modules/source"
install -D -m0644 common_drivers/drivers/media/vfm_cap/vfm_cap.ko "$modules/extra/amlogic/vfm_cap.ko"
strip --strip-debug "$modules/extra/amlogic/vfm_cap.ko"
ln -s usr/lib "$stage/lib"
depmod -b "$stage" "$release"
rm "$stage/lib"
install -D -m0644 arch/arm64/boot/Image "$stage/boot/vmlinuz-$release"
install -m0644 System.map "$stage/boot/System.map-$release"
install -m0644 .config "$stage/boot/config-$release"
for dtb in kvim4 kvim4n; do
    install -D -m0644 "common_drivers/arch/arm64/boot/dts/amlogic/$dtb.dtb" "$stage/boot/dtb-$release/amlogic/$dtb.dtb"
done
mkdir -p "$stage/DEBIAN" "$stage/usr/share/doc/linux-image-vim4-kvm"
cat > "$stage/DEBIAN/control" <<EOF
Package: linux-image-vim4-kvm
Version: $version
Architecture: arm64
Maintainer: VIM4 KVM <318096335+localhost-copilot@users.noreply.github.com>
Section: kernel
Priority: optional
Depends: kmod, initramfs-tools
Description: VIM4 KVM kernel, device trees and modules
EOF
cat > "$stage/DEBIAN/postinst" <<EOF
#!/bin/sh
set -eu
if [ "\$1" = configure ]; then depmod -a '$release'; fi
sync
EOF
chmod 0755 "$stage/DEBIAN/postinst"
cp COPYING "$stage/usr/share/doc/linux-image-vim4-kvm/copyright"
python3 - "$stage/usr/share/doc/linux-image-vim4-kvm/build.json" "$kernel_commit" "$driver_commit" <<'PY'
import hashlib, json, pathlib, subprocess, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(kernel=sys.argv[2], drivers=sys.argv[3],
    config_sha256=hashlib.sha256(pathlib.Path('.config').read_bytes()).hexdigest(),
    compiler=subprocess.check_output(['gcc-12','--version'],text=True).splitlines()[0]),indent=2)+'\n')
PY
dpkg-deb --root-owner-group --build "$stage" "$package"
cp "$stage/usr/share/doc/linux-image-vim4-kvm/build.json" "$output/kernel-build.json"
(cd "$output" && sha256sum "$(basename "$package")" > "$(basename "$package").sha256")
