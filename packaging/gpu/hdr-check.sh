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
cc -O2 -Wall -Wextra -Werror /repo/packaging/gpu/hdr-probe.c -o /out/hdr-probe -lEGL -lGLESv2 -lgbm
glslangValidator -S comp /repo/packaging/gpu/hdr.comp
python3 /repo/packaging/gpu/hdr-vulkan.py /repo/packaging/gpu/hdr.comp /out/hdr-vulkan.comp
glslangValidator -V /out/hdr-vulkan.comp -o /out/hdr-vulkan.spv
spirv-val /out/hdr-vulkan.spv
cc -std=c11 -Wall -Wextra -Werror -shared -fPIC /repo/packaging/gpu/hdr-dmabuf.c -lvulkan -o /out/libhdr-dmabuf.so
cc -std=c11 -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
 /repo/packaging/gpu/hdr-dmabuf.c /repo/packaging/gpu/hdr-dmabuf-test.c \
 -Wl,--gc-sections -o /out/hdr-dmabuf-test
/out/hdr-dmabuf-test
EGL_PLATFORM=surfaceless LIBGL_ALWAYS_SOFTWARE=1 GPU_HDR_ALLOW_SOFTWARE=1 \
 python3 /repo/packaging/gpu/hdr-check.py /out/hdr-probe /repo/packaging/gpu/hdr.comp /out/check
sha256sum /out/hdr-probe /repo/packaging/gpu/hdr.comp
'
