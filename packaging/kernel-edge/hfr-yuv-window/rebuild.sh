#!/bin/bash
# Rebuild the review-sensitive subset. All compiler writes stay in our task dirs.
set -eu -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../../.."
kernel=${1:?supply the integrated kernel SHA}
encoder=${2:?supply the hfr120 gst-plugin-venc SHA}
onekvm=${3:-}
if [ "${4:-}" != inside-heavy ]; then
    exec tools/board-queue run --heavy --who hfr-yuv-window --purpose rebuild --max-min 30 -- bash "$here/rebuild.sh" "$kernel" "$encoder" "$onekvm" inside-heavy
fi
b=$PWD/build/hfr-yuv-window
stage=$(mktemp -d "$b/rebuild.XXXXXX")
repo=../vim4-kvm-hfr120/gst-plugin-venc
git -C "$repo" archive "$encoder" | tar -xf - -C "$stage"
orb -m vim4-build bash -eu "$here/kernel.sh" "$kernel" "$stage"
docker run --rm --network none -v "$stage:/work" -v "$PWD/packaging:/recipe:ro" \
    -v "$b/src/archive.xz:/archive.xz:ro" -w /work vim4-kvm-builder:ubuntu24.04 bash -ec '
    make -C wave5 -j4 libgstvim4wave5.so
    make -C hdr libgstvim4hevc10.so
    cc -O2 -Wall -Wextra -Werror /recipe/kernel-edge/hfr-yuv-window/raw-pool.c -o raw-pool
    cd /tmp
    echo "6e347c72d4b8b2886d890ffe9f6767a9edb02f201588e8c3a572dcd08d9852bd  /archive.xz" | sha256sum -c -
    tar -xf /archive.xz
    cd gst-plugins-good-1.24.2
    python3 /recipe/kernel-edge/hfr-yuv-window/patch-gst.py
    meson setup build -Dauto_features=disabled -Dv4l2=enabled -Dtests=disabled -Dexamples=disabled -Ddoc=disabled -Dnls=disabled
    ninja -C build -j4 sys/v4l2/libgstvideo4linux2.so
    cp build/sys/v4l2/libgstvideo4linux2.so /work/'
expected=$(python3 -c 'import tomllib;print(tomllib.load(open("packaging/kernel-edge/sources.toml","rb"))["gstreamer"]["candidate_plugin_sha256"])')
echo "$expected  $stage/libgstvideo4linux2.so" | shasum -a 256 -c -
if [ -n "$onekvm" ]; then
    app=../vim4-kvm-hfr120/One-KVM
    mkdir "$stage/One-KVM"
    git -C "$app" archive "$onekvm" | tar -xf - -C "$stage/One-KVM"
    if git -C "$app" diff --quiet 3c7d1a7f "$onekvm" -- web; then
        cp -R "$b/src/One-KVM/web/dist" "$stage/One-KVM/web/"
    fi
    docker run --rm --network none -v "$stage/One-KVM:/work" -v "$stage:/out" \
        -v onekvm-managed-cargo:/cargo:ro -v hdr10-p0-5-cargo-target:/previous:ro \
        -e CARGO_HOME=/cargo -e CARGO_TARGET_DIR=/target -w /work vim4-kvm-builder:ubuntu24.04 bash -ec '
        if ! test -f web/dist/index.html; then npm ci --offline --prefix web && npm --prefix web run build; fi
        mkdir -p /target && cp -a /previous/release /target/
        cargo build -j6 --offline --locked --release --features vim4 --bin one-kvm
        cp /target/release/one-kvm /out/onekvm-candidate'
    cp "$stage/onekvm-candidate" "$b/payload/one-kvm"
fi
cp "$stage"/*.ko "$stage"/{hdr,wave5}/*.so "$stage"/libgstvideo4linux2.so "$stage/raw-pool" \
    tools/{hdmirx-encode-check,edge-jpeg-check}.py "$b/payload/"
(cd "$b/payload"; shasum -a 256 *.ko *.so *.py *.so.0 v4l2-ctl capture-integrity raw-pool vim4-driver-bench one-kvm > SHA256SUMS)
