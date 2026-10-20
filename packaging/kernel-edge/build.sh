#!/bin/bash
# Compile the experimental kernel into an external directory; never install it.
set -euo pipefail
source_dir=$(realpath "${1:?kernel source directory required}")
output=$(realpath -m "${2:?external build directory required}")
recipe=$(cd "$(dirname "$0")" && pwd)
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'Requires Linux ARM64' >&2; exit 1; }
python3 - "$recipe" "$source_dir" "$output" <<'PY'
import pathlib, subprocess, sys, tomllib
recipe, source, output = map(pathlib.Path, sys.argv[1:])
lock = tomllib.loads((recipe / 'sources.toml').read_text())
if output == source or output.is_relative_to(source):
    raise SystemExit('Build output must be outside the kernel source tree')
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip()
if revision != lock['kernel']['revision'] or dirty:
    raise SystemExit('Kernel revision differs from sources.toml or working tree is dirty')
if output.exists() and any(output.iterdir()):
    raise SystemExit('Use a new empty output directory to avoid mixing configurations')
PY
mkdir -p "$output"
cp "$recipe/edge.config" "$output/.config"
export SOURCE_DATE_EPOCH=$(git -C "$source_dir" show -s --format=%ct HEAD)
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH")
args=(-C "$source_dir" O="$output" ARCH=arm64 CC=gcc KBUILD_BUILD_VERSION=1 KBUILD_BUILD_USER=vim4-kvm KBUILD_BUILD_HOST=vim4-build)
make "${args[@]}" olddefconfig
make "${args[@]}" -j"${JOBS:-8}" Image dtbs modules
python3 - "$source_dir" "$output" <<'PY'
import hashlib, json, pathlib, subprocess, sys
source, output = map(pathlib.Path, sys.argv[1:])
artifacts = ['.config', 'arch/arm64/boot/Image',
             'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4.dtb',
             'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-udc-test.dtb',
             'arch/arm64/boot/dts/amlogic/amlogic-t7-a311d2-khadas-vim4-hdmirx-test.dtb']
report = {
    'kernel': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
    'compiler': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
    'sha256': {p: hashlib.sha256((output / p).read_bytes()).hexdigest() for p in artifacts},
    'validation': 'Image, dtbs and modules built; hardware not tested',
}
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
PY
