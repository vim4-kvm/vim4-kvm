FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
ENV DEBIAN_FRONTEND=noninteractive TZ=UTC LC_ALL=C.UTF-8
ADD --checksum=sha256:641de77d8f142cfd62a1a6f964ba67b20754d3337c480efb529d086075a06c9a https://snapshot.ubuntu.com/ubuntu/20261012T000000Z/pool/main/c/ca-certificates/ca-certificates_20240203_all.deb /tmp/ca-certificates.deb
RUN dpkg-deb -x /tmp/ca-certificates.deb / \
 && mkdir -p /etc/ssl/certs \
 && cat /usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt \
 && rm /tmp/ca-certificates.deb
RUN test "$(dpkg --print-architecture)" = arm64 \
 && rm /etc/apt/sources.list.d/ubuntu.sources \
 && printf 'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg check-valid-until=no] http://snapshot.ubuntu.com/ubuntu/20261012T000000Z %s main universe\n' noble noble-updates noble-security > /etc/apt/sources.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates curl xz-utils git build-essential gcc-12 pkg-config python3 \
    meson ninja-build libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    libopus-dev libdrm-dev dpkg-dev file sudo libssl-dev bc bison flex \
    device-tree-compiler kmod rsync clang libclang-dev cmake nasm \
    libavcodec-dev libavutil-dev libavformat-dev libyuv-dev libasound2-dev \
    libudev-dev libdbus-1-dev libsodium-dev libturbojpeg0-dev \
 && rm -rf /var/lib/apt/lists/*
COPY downloads.lock.json fetch.py /opt/build-inputs/
RUN python3 /opt/build-inputs/fetch.py /opt/build-inputs/downloads.lock.json /opt/downloads \
 && tar -xzf /opt/downloads/go.tar.gz -C /opt \
 && tar -xJf /opt/downloads/rust.tar.xz -C /tmp \
 && /tmp/rust-1.99.0-aarch64-unknown-linux-gnu/install.sh --prefix=/opt/rust --disable-ldconfig --without=rust-docs \
 && rm -rf /tmp/rust-1.99.0-aarch64-unknown-linux-gnu \
 && mkdir /opt/node /opt/pnpm \
 && tar -xJf /opt/downloads/node.tar.xz -C /opt/node --strip-components=1 \
 && tar -xzf /opt/downloads/pnpm.tgz -C /opt/pnpm --strip-components=1 \
 && for package in /opt/downloads/*.deb; do dpkg-deb -x "$package" /; done \
 && ldconfig \
 && dpkg-query -W > /opt/build-inputs/ubuntu-packages.txt
ENV PATH=/opt/rust/bin:/opt/go/bin:/opt/node/bin:/opt/pnpm/bin:$PATH GOTOOLCHAIN=local
RUN ln -s /opt/pnpm/bin/pnpm.mjs /opt/node/bin/pnpm
RUN apt-get update && apt-get install -y --no-install-recommends \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
 && dpkg-query -W > /opt/build-inputs/ubuntu-packages.txt \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
RUN chmod 0755 /opt/pnpm/bin/pnpm.mjs && pnpm --version && go version && node --version
