# EntryNav plugin build + emulated test image.
#
# Reproduces the head unit's toolchain (Ubuntu/Linaro GCC 4.7.2, eglibc 2.15, libstdc++ 6.0.17 ->
# GLIBCXX_3.4.17 - an exact ABI match to the car) on a modern, pullable base, plus qemu-user so an
# ARM plugin can be built and load-tested against the dumped rootfs without touching the car.
#
# The repo's original toolchain (FROM ubuntu:12.10) no longer builds: that image uses a v1 manifest
# modern Docker refuses. We fetch the same 4.7 cross .debs straight from the quantal archive instead.
#
# Build:  docker build --platform linux/amd64 -t entrynav-tc hmitest
# (must be linux/amd64: the amd64 GCC-4.7 binaries run under emulation on Apple Silicon.)
FROM --platform=linux/amd64 debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates python3 dpkg binutils make file qemu-user-static \
 && rm -rf /var/lib/apt/lists/*

# Fetch + extract the car's GCC 4.7 armhf cross toolchain into /opt/tc.
COPY fetch_toolchain.py /tmp/
RUN python3 /tmp/fetch_toolchain.py \
 && ln -sfn /opt/tc/usr/arm-linux-gnueabihf /usr/arm-linux-gnueabihf \
 && mkdir -p /usr/lib/gcc \
 && ln -sfn /opt/tc/usr/lib/gcc/arm-linux-gnueabihf /usr/lib/gcc/arm-linux-gnueabihf

# PATH to the cross binaries; LD_LIBRARY_PATH to the amd64 helper libs they need
# (libbfd/libopcodes for as/ld, libmpfr.so.4/libmpc.so.2 for cc1/cc1plus).
ENV PATH=/opt/tc/usr/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/tc/usr/x86_64-linux-gnu/arm-linux-gnueabihf/lib:/opt/tc/usr/lib/x86_64-linux-gnu
ENV SYSROOT=/sysroot

# Prebuild the load-test harness (ARM) so test-plugin.sh just runs it under qemu.
COPY plugin_load_check.c /opt/harness/
RUN arm-linux-gnueabihf-gcc-4.7 -O2 -Wall /opt/harness/plugin_load_check.c -ldl \
      -o /opt/harness/plugin_load_check \
 && file /opt/harness/plugin_load_check

WORKDIR /work
