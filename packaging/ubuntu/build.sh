#!/bin/sh
# Runs only inside the isolated Ubuntu builder. Source mount is read-only.
set -eu
rsync -a --exclude=.git --exclude=node_modules --exclude=build --exclude=dist \
    --exclude=logs --exclude=__pycache__ --exclude=/common_drivers/ --exclude=/NanoKVM-Pro/ \
    /src/ /work/
cd /work
mkdir -p build
cc -O2 -Wall -Wextra -Werror tools/usb-pd-init.c -o build/usb-pd-init
cc -Wall -Wextra -Werror tests/pd-request.c -o build/pd-test
build/pd-test
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s NanoKVM/deploy/vim4 -p 'test_*.py'
python3 -m unittest discover -s vim4-manager/deploy -p 'test_*.py'
python3 -m unittest discover -s kvm/deploy/vim4 -p 'test_*.py'
python3 tools/workspace.py build all
cd NanoKVM/server
cc -shared -fPIC -Iinclude /work/tests/kvm-abi-stub.c -o dl_lib/libkvm.so
LD_LIBRARY_PATH="$PWD/dl_lib" go test ./...
go build -o /work/build/NanoKVM-Server-default-check .
cd /work
for helper in NanoKVM/deploy/vim4/*.sudoers vim4-manager/deploy/*.sudoers kvm/deploy/vim4/*.sudoers; do visudo -cf "$helper"; done
python3 packaging/ubuntu/package.py "$PACKAGE_VERSION" /out
