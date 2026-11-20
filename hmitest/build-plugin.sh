#!/bin/bash
# Run a build command in the car-matched GCC-4.7 toolchain image, with your sources on /work and the
# dumped rootfs on /sysroot (read-only). Equivalent of the repo's toolchain/tc.sh, but on a base that
# still builds. The cross compiler is arm-linux-gnueabihf-g++-4.7 (CXX) and SYSROOT=/sysroot.
#
# Examples:
#   # build the reference AA plugin from the repo:
#   hmitest/build-plugin.sh ~/Documents/EntryNav2-Android-Auto make hmiapp CXX=arm-linux-gnueabihf-g++-4.7
#   # one-off compile of your own plugin:
#   hmitest/build-plugin.sh ~/my-plugin arm-linux-gnueabihf-g++-4.7 -std=gnu++0x -O2 \
#       -march=armv7-a -mfpu=neon -mfloat-abi=hard -fPIC -fvisibility=hidden -shared \
#       -Wl,-soname,libMyPlugin.so my_plugin.cpp -o libMyPlugin.so \
#       -L/sysroot/opt/hmi/lib -Wl,-rpath-link,/sysroot/opt/hmi/lib \
#       -L/sysroot/usr/lib -L/sysroot/lib -l:libAppFramework.A.so -l:libCoreFramework.A.so -lpthread -ldl
set -euo pipefail
WORK="${1:?usage: build-plugin.sh <work-dir> <command...>}"; shift
ROOTFS="${HU_ROOTFS:-/Volumes/hurootfs/rootfs-202402191339}"
IMAGE="${IMAGE:-entrynav-tc}"
WORK=$(cd "$WORK" && pwd)
[ -d "$ROOTFS/opt/hmi/lib" ] || { echo "rootfs not found at $ROOTFS (set HU_ROOTFS)" >&2; exit 2; }
exec docker run --rm --platform linux/amd64 \
  -u "$(id -u):$(id -g)" -v "$WORK:/work" -v "$ROOTFS:/sysroot:ro" -w /work "$IMAGE" "$@"
