ARG BASE=vim4-package-builder:70b379fe46a6dbf694ed7657af691f03ede638ca56e727fae08e218fa663f76f
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
 llvm-19-dev clang-19 libclang-19-dev libclc-19-dev libclc-19 \
 libllvmspirvlib-19-dev spirv-tools spirv-headers \
 libglvnd-dev libexpat1-dev libelf-dev libzstd-dev zlib1g-dev \
 libwayland-dev wayland-protocols libudev-dev python3-mako python3-yaml \
 python3-packaging python3-pip python3-venv libvulkan-dev vulkan-tools \
 clinfo libegl-dev libgles-dev ocl-icd-opencl-dev glmark2-es2 \
 clpeak ninja-build patchelf \
 && python3 -m venv --system-site-packages /opt/gpu-python \
 && /opt/gpu-python/bin/pip install meson==1.9.2 \
 && cargo install bindgen-cli --version 0.71.1 --locked \
 && dpkg-query -W > /opt/gpu-packages.txt
ENV PATH=/opt/gpu-python/bin:/root/.cargo/bin:/opt/rust/bin:/usr/lib/llvm-19/bin:${PATH}
ENV LLVM_CONFIG=llvm-config-19 LIBCLANG_PATH=/usr/lib/llvm-19/lib
COPY downloads.lock.json /opt/gpu-downloads.lock.json
RUN curl -fL https://archive.mesa3d.org/mesa-26.2.6.tar.xz -o /opt/mesa.tar.xz \
 && echo 'b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92  /opt/mesa.tar.xz' | sha256sum -c - \
 && tar -xf /opt/mesa.tar.xz -C /opt \
 && cd /opt/mesa-26.2.6 \
 && meson subprojects download $(for wrap in subprojects/*-rs.wrap; do basename "$wrap" .wrap; done) \
 && find subprojects/packagecache -type f -exec sha256sum {} \; > /opt/gpu-subprojects.sha256
RUN apt-get install -y --no-install-recommends vkmark \
 && dpkg-query -W > /opt/gpu-packages.txt
RUN apt-get install -y --no-install-recommends libwayland-egl-backend-dev \
 && dpkg-query -W > /opt/gpu-packages.txt
