#!/bin/sh
# Run inside the isolated ARM64 PiKVM builder.
set -eu
test "$(dpkg --print-architecture)" = arm64
mkdir -p /work/janus
tar -xzf /opt/pikvm-inputs/janus.tar.gz -C /work/janus --strip-components=1
cd /work/janus
patch -p1 < /opt/pikvm-inputs/janus-js.patch
./autogen.sh
./configure --prefix=/usr --sysconfdir=/etc \
    --disable-docs --disable-data-channels --disable-turn-rest-api \
    --disable-all-plugins --disable-all-loggers --disable-all-transports \
    --enable-websockets --disable-sample-event-handler \
    --disable-websockets-event-handler --disable-gelf-event-handler
make -j"$(nproc)"
make install
install -m644 /opt/pikvm-inputs/adapter.js /usr/share/janus/javascript/adapter.js
pkg-config --modversion janus-gateway
