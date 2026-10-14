ARG BASE_IMAGE=vim4-kvm-builder:ubuntu24.04
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake libtool gengetopt libglib2.0-dev libjansson-dev \
    libconfig-dev libwebsockets-dev libnice-dev libsrtp2-dev libspeexdsp-dev \
    python3-websocket \
 && dpkg-query -W > /opt/build-inputs/ubuntu-packages.txt \
 && rm -rf /var/lib/apt/lists/*
COPY pikvm/downloads.lock.json /opt/build-inputs/pikvm-downloads.lock.json
RUN python3 /opt/build-inputs/fetch.py /opt/build-inputs/pikvm-downloads.lock.json /opt/pikvm-inputs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libevent-dev libbsd-dev libjpeg-dev libffi-dev libbz2-dev liblzma-dev \
    libreadline-dev libsqlite3-dev zlib1g-dev libsystemd-dev libxkbcommon0 \
    libfreetype6-dev nginx \
 && dpkg-query -W > /opt/build-inputs/ubuntu-packages.txt \
 && rm -rf /var/lib/apt/lists/*
RUN mkdir /tmp/python && tar -xJf /opt/pikvm-inputs/python.tar.xz -C /tmp/python --strip-components=1 \
 && cd /tmp/python && ./configure --prefix=/opt/vim4-pikvm/python --with-ensurepip=install \
 && make -j8 && make install && rm -rf /tmp/python
COPY pikvm/bootstrap.lock pikvm/requirements.lock /opt/build-inputs/
RUN /opt/vim4-pikvm/python/bin/python3.14 -m pip install --require-hashes -r /opt/build-inputs/bootstrap.lock \
 && /opt/vim4-pikvm/python/bin/python3.14 -m pip install --require-hashes --no-build-isolation -r /opt/build-inputs/requirements.lock
