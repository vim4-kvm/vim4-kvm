#!/bin/bash
# Run inside the sealed ARM64 builder with --network none. No hardware access.
set -euo pipefail
recipe=/repo/packaging/gpu
cd /output
test ! -e stage
echo 'b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92  /inputs/mesa.tar.xz' | sha256sum -c -
cp -a /opt/mesa-26.2.6 .
variant=${GPU_VARIANT:-loop-codegen}
runtime_name=vim4-mesa-26.2.6
changes=()
case "$variant" in
 baseline) ;;
 bounded-unroll)
  changes=(0001-nir-bounded-bifrost-unroll.patch 0002-nir-test-unroll-cost.patch)
  runtime_name=vim4-mesa-26.2.6-unroll1 ;;
 loop-codegen)
  changes=(0003-bifrost-loop-invariants.patch)
  runtime_name=vim4-mesa-26.2.6-loop2 ;;
 loop-layout)
  changes=(0003-bifrost-loop-invariants.patch 0004-bifrost-jump-cleanup.patch 0005-bifrost-uniform-backedges.patch)
  runtime_name=vim4-mesa-26.2.6-layout2 ;;
 loop-jumps)
  changes=(0003-bifrost-loop-invariants.patch 0004-bifrost-jump-cleanup.patch)
  runtime_name=vim4-mesa-26.2.6-jumps2 ;;
 *) echo 'Unknown GPU_VARIANT' >&2; exit 2 ;;
esac
for change in "${changes[@]}"; do
 (cd mesa-26.2.6 && git apply "$recipe/patches/$change")
done
export SOURCE_DATE_EPOCH=1793145600
export PYTHONHASHSEED=0
meson setup build mesa-26.2.6 --wrap-mode=nodownload \
 --prefix=/opt/"$runtime_name" --libdir=lib --buildtype=release \
 -Dgallium-drivers=panfrost -Dvulkan-drivers=panfrost -Dgallium-rusticl=true \
 -Dllvm=enabled -Dplatforms=wayland -Degl=enabled -Dgbm=enabled \
 -Dgles2=enabled -Dglx=disabled -Dglvnd=enabled -Dbuild-tests=true \
 -Dtools=drm-shim,panfrost -Dstatic-libclc=all -Dmesa-clc-bundle-headers=enabled
meson compile -C build -j4
meson test -C build --print-errorlogs --num-processes 4
DESTDIR=/output/stage meson install -C build
prefix=/output/stage/opt/$runtime_name
mkdir -p "$prefix/bin"
cc -O2 -Wall -Wextra -Werror "$recipe/gpu-probe.c" -o "$prefix/bin/gpu-probe" -lEGL -lGLESv2 -lgbm
cp /usr/bin/clinfo /usr/bin/clpeak /usr/bin/vulkaninfo /usr/bin/vkmark "$prefix/bin/"
cp -a /usr/share/vkmark "$prefix/share/"
cp -a /usr/lib/aarch64-linux-gnu/vkmark "$prefix/lib/"
cp "$recipe/../../tools/gpu-compare.py" "$prefix/bin/"
mkdir -p "$prefix/share/build-proof"
mkdir -p "$prefix/share/licenses"
cp -a mesa-26.2.6/licenses "$prefix/share/licenses/mesa"
cp /usr/share/doc/vkmark/copyright "$prefix/share/licenses/vkmark"
cp /usr/share/doc/clpeak/copyright "$prefix/share/licenses/clpeak"
cp /opt/gpu-packages.txt /opt/gpu-subprojects.sha256 "$recipe/builder.lock.json" "$prefix/share/build-proof/"
cp build/meson-logs/testlog.json "$prefix/share/build-proof/"
for change in "${changes[@]}"; do cp "$recipe/patches/$change" "$prefix/share/build-proof/"; done
meson introspect build --buildoptions > "$prefix/share/build-proof/options.json"
python3 "$recipe/package.py" "$prefix"
cp /opt/gpu-packages.txt manifest-packages.txt
meson introspect build --buildoptions > manifest-options.json
archive=${runtime_name#vim4-}-arm64.tar.xz
tar --sort=name --mtime=@1793145600 --owner=0 --group=0 --numeric-owner -cJf "$archive" -C stage opt
sha256sum "$archive" > archive.sha256
