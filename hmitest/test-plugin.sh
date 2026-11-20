#!/bin/bash
# Load-test an RHMI plugin .so under QEMU against the car's dumped libraries - the pre-ship check.
# It does NOT run on the car and does NOT call the plugin's create(); it verifies the plugin loads
# with every symbol resolved against the real firmware, exports a valid pluginAppInfo, and that this
# firmware's bmw::PluginApp vtable still has onError/onInit/onFinalize at slots 21/22/23.
#
# Usage:  hmitest/test-plugin.sh <plugin.so>
#         HU_ROOTFS=/path/to/rootfs hmitest/test-plugin.sh <plugin.so>
# Build the image first:  docker build --platform linux/amd64 -t entrynav-tc hmitest
set -euo pipefail
PLUGIN="${1:?usage: test-plugin.sh <plugin.so>}"
ROOTFS="${HU_ROOTFS:-/Volumes/hurootfs/rootfs-202402191339}"
IMAGE="${IMAGE:-entrynav-tc}"
[ -f "$PLUGIN" ] || { echo "no such file: $PLUGIN" >&2; exit 2; }
[ -d "$ROOTFS/opt/hmi/lib" ] || { echo "rootfs not found at $ROOTFS (set HU_ROOTFS)" >&2; exit 2; }
PDIR=$(cd "$(dirname "$PLUGIN")" && pwd); PBASE=$(basename "$PLUGIN")
GUEST_LD=/opt/hmi/lib:/usr/local/lib:/usr/lib:/lib
exec docker run --rm --platform linux/amd64 \
  -v "$ROOTFS:/sysroot:ro" -v "$PDIR:/plug:ro" "$IMAGE" \
  qemu-arm-static -L /sysroot -E LD_LIBRARY_PATH="$GUEST_LD" \
  /opt/harness/plugin_load_check "/plug/$PBASE"
