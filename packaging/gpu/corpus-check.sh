#!/bin/bash
# Offline shader-db comparison inside the ARM64 builder. No GPU devices.
set -euo pipefail
if [[ $# != 5 ]]; then
 echo "Usage: $0 BASELINE_PREFIX CANDIDATE_PREFIX SHIM INPUT_DIR OUTPUT_DIR" >&2
 exit 2
fi
baseline=$1 candidate=$2 shim=$3 inputs=$4 output=$5
mkdir -p "$output"
cd "$inputs"
echo 'c32024f380407a9aec409cabfbd52bfc97f33d8952fa264a525f464d5c486f99  shader-db-pinned.tar.gz' | sha256sum -c -
echo '976557dd0a474f859db69f092c15ae83c366c7a42400be45ccf7921b314c257f  corpus-deps/libepoxy-dev_1.5.10-1build1_arm64.deb' | sha256sum -c -
echo '103381283fcdbb4af06c155568c1e945f0a647d75f2522e0c2418ebb70b855ba  corpus-deps/libepoxy0_1.5.10-1build1_arm64.deb' | sha256sum -c -
for package in corpus-deps/*.deb; do dpkg-deb -x "$package" "$output/deps"; done
source_root=shader-db-6ec450899fb1cb9d6d4829bbf864288c4e7a5dbb
mkdir -p "$output/shader-db-main"
tar -xzf shader-db-pinned.tar.gz --strip-components=1 -C "$output/shader-db-main" \
 "$source_root/run.c" "$source_root/Makefile" "$source_root/COPYING" "$source_root/shaders"
cd "$output/shader-db-main"
cc -O2 -fopenmp -I"$output/deps/usr/include" run.c \
 -L"$output/deps/usr/lib/aarch64-linux-gnu" -lepoxy -lgbm -o run
for variant in baseline candidate; do
 prefix=$baseline
 [[ $variant == candidate ]] && prefix=$candidate
 result=0
 timeout -k 5 600 env LD_LIBRARY_PATH="$prefix/lib:$output/deps/usr/lib/aarch64-linux-gnu" \
  LIBGL_DRIVERS_PATH="$prefix/lib/dri" \
  __EGL_VENDOR_LIBRARY_FILENAMES="$prefix/share/glvnd/egl_vendor.d/50_mesa.json" \
  LD_PRELOAD="$shim" PAN_GPU_ID=0x7402 BIFROST_MESA_DEBUG=shaderdb \
  MESA_SHADER_CACHE_DISABLE=true ./run -j 1 -o panfrost shaders \
  > "$output/$variant.out" 2> "$output/$variant.err" || result=$?
 echo "$result" > "$output/$variant.exit"
done
test "$(cat "$output/baseline.exit")" = 0
test "$(cat "$output/candidate.exit")" = 0
grep -q 'MESA_SHADER_' "$output/baseline.out"
grep -q 'MESA_SHADER_' "$output/candidate.out"
sha256sum "$output"/*.out "$output"/*.err > "$output/logs.sha256"
