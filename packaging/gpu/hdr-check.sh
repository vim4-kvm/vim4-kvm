#!/bin/bash
# Host entry: locked ARM64 builder; software GLES only, no board or network.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
output=${1:-"$repo/build/gpu-hdr"}
mkdir -p "$output"
output=$(cd "$output" && pwd)
builder=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$repo/packaging/gpu/builder.lock.json")
docker run --rm --network none -v "$repo:/repo:ro" -v "$output:/out" "$builder" bash -lc '
set -e
cc -O2 -Wall -Wextra -Werror /repo/packaging/gpu/hdr-probe.c -o /out/hdr-probe -lEGL -lGLESv2
glslangValidator -S comp /repo/packaging/gpu/hdr.comp
EGL_PLATFORM=surfaceless LIBGL_ALWAYS_SOFTWARE=1 GPU_HDR_ALLOW_SOFTWARE=1 \
 python3 /repo/packaging/gpu/hdr-check.py /out/hdr-probe /repo/packaging/gpu/hdr.comp /out/check
sha256sum /out/hdr-probe /repo/packaging/gpu/hdr.comp
'
