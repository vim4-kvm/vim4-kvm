#!/bin/sh
# Runs only inside the isolated Ubuntu builder. Source mount is read-only.
set -eu
COMPONENT=${COMPONENT:-all}
rsync -a --exclude=.git --exclude=node_modules --exclude=build --exclude=dist \
    --exclude=logs --exclude=__pycache__ --exclude=target --exclude=/common_drivers/ \
    /src/ /work/
cd /work
mkdir -p build
python3 -m unittest discover -s tests -p 'test_*.py'
has() { [ "$COMPONENT" = all ] || [ "$COMPONENT" = "$1" ] || { [ "$COMPONENT" = onekvm-board ] && [ "$1" = onekvm ]; }; }
if has platform || [ "$COMPONENT" = onekvm-board ]; then
    cc -O2 -Wall -Wextra -Werror tools/usb-pd-init.c -o build/usb-pd-init
    cc -Wall -Wextra -Werror tests/pd-request.c -o build/pd-test
    build/pd-test
fi
if has platform || has capture; then
    python3 tools/workspace.py build capture
    meson test -C gst-plugin-vfmcap/build --print-errorlogs
fi
if has platform || has encoder; then
    # The source contract test parses the real HDR chain in NULL state. A
    # platform build includes its companion capture plugin without devices.
    GST_PLUGIN_PATH="$PWD/gst-plugin-vfmcap/build${GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}" \
        python3 tools/workspace.py build encoder
fi
if has platform || has encoder || has onekvm || has capture; then
    gst_work=$(mktemp -d)
    trap 'rm -rf "$gst_work"' EXIT
    python3 packaging/kernel-edge/build-gstreamer.py "$gst_work"
    mkdir -p build/mainline-gstreamer
    cp "$gst_work/libgstvideo4linux2.so" build/mainline-gstreamer/
    rm -rf "$gst_work"
    trap - EXIT
fi
if has nanokvm; then
    python3 -m unittest discover -s NanoKVM/deploy/vim4 -p 'test_*.py'
    python3 tools/workspace.py build server
    python3 tools/workspace.py build frontend
    node --test NanoKVM/web/tests/hevc.mjs
    cd NanoKVM/server
    cc -shared -fPIC -Iinclude /work/tests/kvm-abi-stub.c -o dl_lib/libkvm.so
    LD_LIBRARY_PATH="$PWD/dl_lib" go test ./...
    go build -o /work/build/NanoKVM-Server-default-check .
    cd /work
    for helper in NanoKVM/deploy/vim4/*.sudoers; do visudo -cf "$helper"; done
fi
if has jetkvm; then
    python3 -m unittest discover -s kvm/deploy/vim4 -p 'test_*.py'
    python3 tools/workspace.py build jetkvm
    for helper in kvm/deploy/vim4/*.sudoers; do visudo -cf "$helper"; done
fi
if has onekvm; then
    python3 -m unittest discover -s One-KVM/deploy/vim4 -p 'test_*.py'
    python3 tools/workspace.py build onekvm
    for helper in One-KVM/deploy/vim4/*.sudoers; do visudo -cf "$helper"; done
fi
if has manager; then
    python3 -m unittest discover -s vim4-manager/deploy -p 'test_*.py'
    python3 tools/workspace.py build manager
    for helper in vim4-manager/deploy/*.sudoers; do visudo -cf "$helper"; done
fi
python3 packaging/ubuntu/package.py "$PACKAGE_VERSION" /out "$COMPONENT"
