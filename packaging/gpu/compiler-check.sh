#!/bin/bash
# Offline container only: drm-shim compiles G52 shaders but cannot render pixels.
set -euo pipefail
runtime=/output/stage/opt/vim4-mesa-26.2.6
test -e /opt/vim4-mesa-26.2.6 || ln -s "$runtime" /opt/vim4-mesa-26.2.6
status=0
timeout 40 env EGL_PLATFORM=surfaceless LD_LIBRARY_PATH="$runtime/lib" \
 LIBGL_DRIVERS_PATH="$runtime/lib/dri" \
 __EGL_VENDOR_LIBRARY_FILENAMES="$runtime/share/glvnd/egl_vendor.d/50_mesa.json" \
 LD_PRELOAD=/output/build/src/panfrost/drm-shim/libpanfrost_noop_drm_shim.so \
 PAN_GPU_ID=0x7402 MESA_SHADER_CACHE_DISABLE=true BIFROST_MESA_DEBUG=shaders \
 "$runtime/bin/gpu-probe" 0.01 > /output/g52-compiler.log 2>&1 || status=$?
test "$status" = 1 # Pixel validation must fail: noop does not execute jobs.
grep -q 'Mali-G52 r1 MC4 (Panfrost)' /output/g52-compiler.log
grep -q 'shader: MESA_SHADER_VERTEX' /output/g52-compiler.log
grep -q 'shader: MESA_SHADER_FRAGMENT' /output/g52-compiler.log
grep -q 'gl_error=0' /output/g52-compiler.log
echo 'G52 vertex/fragment compiler path passed; noop pixel validation failed as expected'
