#!/bin/bash
# Compare compilers inside the sealed builder; noop output is not a benchmark.
set -euo pipefail
if [[ $# != 5 ]]; then
 echo "Usage: $0 BASELINE_PREFIX CANDIDATE_PREFIX SHIM PROBE OUTPUT_DIR" >&2
 exit 2
fi
baseline=$1 candidate=$2 shim=$3 probe=$4 output=$5
mkdir -p "$output"
for variant in baseline candidate; do
 prefix=$baseline
 [[ $variant == candidate ]] && prefix=$candidate
 for shader in loop unrolled; do
  options=()
  [[ $shader == unrolled ]] && options+=(GPU_UNROLL128=1)
  for detail in verbose summary; do
   flags=shaders,statsfull
   [[ $detail == summary ]] && flags=shaderdb
   log=$output/$variant-$shader-$detail.log
   result=0
   timeout -k 2 20 env -u GPU_UNROLL128 -u GPU_TIMER_QUERY \
    EGL_PLATFORM=surfaceless LD_LIBRARY_PATH="$prefix/lib" \
    LIBGL_DRIVERS_PATH="$prefix/lib/dri" \
    __EGL_VENDOR_LIBRARY_FILENAMES="$prefix/share/glvnd/egl_vendor.d/50_mesa.json" \
    LD_PRELOAD="$shim" PAN_GPU_ID=0x7402 MESA_SHADER_CACHE_DISABLE=true \
    BIFROST_MESA_DEBUG="$flags" "${options[@]}" \
    "$probe" .01 > "$log" 2>&1 || result=$?
   # Noop submits no work: the probe must compile, then reject the black pixel.
   if [[ $result != 1 ]] || ! grep -q 'renderer=Mali-G52' "$log" \
     || ! grep -q 'MESA_SHADER_FRAGMENT' "$log" || ! grep -q 'gl_error=0' "$log"; then
    echo "Compiler check failed: $variant/$shader (exit $result)" >&2
    exit 1
   fi
  done
 done
done
sha256sum "$output"/*.log > "$output/logs.sha256"
