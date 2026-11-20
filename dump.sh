#!/bin/bash
# dump.sh: copy an EntryNav2 head unit's system to the Mac over SSH (ENET cable), for building and reverse-engineering.
# Read-only on the car: tar streams straight into SSH, nothing is written there, not even in /tmp.
#
#   ./dump.sh                       # root@169.254.1.0, full set (~2.1 GB), then extract
#   ./dump.sh root@192.168.0.10     # another address
#   ./dump.sh --libs-only           # only what building and QEMU need (~0.5 GB): no /opt/hmi/data
#   ./dump.sh --no-extract          # keep the tar only
#   ./dump.sh -y                    # no confirmation prompt
#
# What is copied: bin sbin lib usr etc opt/hmi opt/app. Any other partition mounted inside them (/opt/app/cisu,
# /etc/machine-id) is skipped. Not copied: /opt/navd (maps, own partition), /opt/navi, /opt/iba, /opt/isp, and
# /var/local (paired phones, contacts, settings).
#
# Output, in ./dump next to this script:
#   hu-rootfs-<firmware>.tar        the copy (holds /etc/shadow and BMW firmware: keep it private, never in git)
#   hu-dump-<date>.txt              what was copied, counts, sha256
#   hu-dump-<date>-errors.txt       tar and ssh messages
#   hurootfs.sparseimage            case-sensitive disk image, mounted on /Volumes/hurootfs, holding rootfs-<firmware>
# Then /Volumes/hurootfs/rootfs and ~/entrynav2/rootfs (the repo's default path) link to the extracted copy, with
# its absolute symlinks made relative so they resolve inside the copy (and inside Docker).
set -u

HU="root@169.254.1.0"
PROFILE="full"
EXTRACT=1
ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        -y | --yes) ASSUME_YES=1 ;;
        --libs-only) PROFILE="libs" ;;
        --no-extract) EXTRACT=0 ;;
        -h | --help) sed -n '2,/^set -u/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        -*) echo "unknown option $1 (see --help)" >&2; exit 2 ;;
        *) HU="$1" ;;
    esac
    shift
done

DIR="$(cd "$(dirname "$0")" && pwd)"
DUMP="$DIR/dump"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DUMP"
INFO="$DUMP/hu-dump-$STAMP.txt"
ERR="$DUMP/hu-dump-$STAMP-errors.txt"

# One SSH connection for every step: one password prompt.
CTL="$DUMP/.ssh-$$"
SSH=(ssh -o ConnectTimeout=10 -o ControlMaster=auto -o "ControlPath=$CTL" -o ControlPersist=900)
cleanup() { ssh -o "ControlPath=$CTL" -O exit "$HU" >/dev/null 2>&1; rm -f "$CTL"; }
trap cleanup EXIT

die() { echo "FAIL: $*" >&2; exit 1; }

# ---- runs on the car (BusyBox sh): "plan" describes the dump, "tar" streams it --------------------------------------
# Read into a variable with read -d '' rather than $(cat <<EOF): macOS's bash 3.2 cannot parse a case inside $(...).
read -r -d '' REMOTE <<'EOF'
MODE=$1
PROFILE=$2
cd / || exit 1
case "$PROFILE" in
    libs) SET="bin sbin lib usr etc opt/hmi/bin opt/hmi/lib opt/app" ;;
    *)    SET="bin sbin lib usr etc opt/hmi opt/app" ;;
esac
MNT=""
while read -r dev mnt rest; do
    [ "$mnt" = / ] || MNT="$MNT ${mnt#/}"
done < /proc/mounts
is_mount() { for m in $MNT; do [ "$m" = "$1" ] && return 0; done; return 1; }
has_mount_under() { for m in $MNT; do case "$m" in "$1"/*) return 0 ;; esac; done; return 1; }
# The set, with every other partition left out: a folder holding a mount point is replaced by its children.
expand() {
    for p in "$@"; do
        [ -e "$p" ] || [ -L "$p" ] || continue
        is_mount "$p" && continue
        if [ -d "$p" ] && [ ! -L "$p" ] && has_mount_under "$p"; then
            expand "$p"/* "$p"/.[!.]*
        else
            echo "$p"
        fi
    done
}
ITEMS=$(expand $SET)
case "$MODE" in
    plan)
        echo "version $(head -n 1 /etc/version)"
        for m in $MNT; do
            for s in $SET; do case "$m" in "$s"/*) echo "skipped /$m" ;; esac; done
        done
        kib=0
        for i in $ITEMS; do
            k=$(du -sk "$i" 2>/dev/null | { read -r a b; echo "${a:-0}"; })
            kib=$((kib + k))
        done
        echo "kib $kib"
        echo "entries $(find $ITEMS 2>/dev/null | wc -l)"
        ;;
    tar)
        exec tar -cf - $ITEMS
        ;;
esac
EOF

# ---- 1. plan ----------------------------------------------------------------------------------------------------------
echo "Planning the dump on $HU (read-only)..."
PLAN=$("${SSH[@]}" "$HU" "sh -s -- plan $PROFILE" <<<"$REMOTE" 2>>"$ERR") || die "ssh to $HU failed, see $ERR"
VERSION=$(sed -n 's/^version //p' <<<"$PLAN" | tr -cd 'A-Za-z0-9._-')
KIB=$(sed -n 's/^kib //p' <<<"$PLAN")
ENTRIES=$(sed -n 's/^entries //p' <<<"$PLAN" | tr -d ' ')
SKIPPED=$(sed -n 's/^skipped //p' <<<"$PLAN")
[ -n "$VERSION" ] && [ -n "$KIB" ] && [ -n "$ENTRIES" ] || die "unexpected answer from the car:
$PLAN"
MIB=$((KIB / 1024))

NEED_KIB=$((KIB * (1 + EXTRACT) + 1024 * 1024))
AVAIL_KIB=$(df -k "$DUMP" | awk 'NR == 2 { print $4 }')

echo
echo "  firmware   $VERSION"
echo "  profile    $PROFILE"
echo "  size       $MIB MiB, $ENTRIES entries"
echo "  skipped    $(echo $SKIPPED)  (other partitions)"
echo "  Mac needs  $((NEED_KIB / 1024)) MiB, has $((AVAIL_KIB / 1024)) MiB free in $DUMP"
[ "$AVAIL_KIB" -gt "$NEED_KIB" ] || die "not enough free space on the Mac"
echo
if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Dump it? [y/N] "
    read -r answer
    case "$answer" in y | Y | yes) ;; *) echo "Nothing done."; exit 0 ;; esac
fi

# ---- 2. dump ----------------------------------------------------------------------------------------------------------
TAR="$DUMP/hu-rootfs-$VERSION.tar"
[ -e "$TAR" ] && TAR="$DUMP/hu-rootfs-$VERSION-$STAMP.tar"
"${SSH[@]}" "$HU" true 2>>"$ERR" || die "the SSH connection dropped, see $ERR"
echo "Dumping to $TAR"
START=$(date +%s)
"${SSH[@]}" "$HU" "sh -s -- tar $PROFILE" <<<"$REMOTE" >"$TAR" 2>>"$ERR" &
pid=$!
while kill -0 "$pid" 2>/dev/null; do
    size=$(stat -f %z "$TAR" 2>/dev/null || echo 0)
    printf '\r  %5d / ~%d MiB' $((size / 1048576)) "$MIB"
    sleep 2
done
wait "$pid"
rc=$?
size=$(stat -f %z "$TAR")
printf '\r  %5d MiB in %d s          \n' $((size / 1048576)) $(($(date +%s) - START))
[ "$rc" -eq 0 ] || die "the dump stopped (exit $rc), see $ERR"

# ---- 3. check ---------------------------------------------------------------------------------------------------------
echo "Checking the tar..."
TAR_ENTRIES=$(tar -tf "$TAR" 2>>"$ERR" | wc -l | tr -d ' ')
[ "$TAR_ENTRIES" -gt 0 ] || die "the tar cannot be read, see $ERR"
SHA=$(shasum -a 256 "$TAR" | awk '{ print $1 }')
echo "  entries: car $ENTRIES, tar $TAR_ENTRIES"
if [ "$TAR_ENTRIES" -lt $((ENTRIES - ENTRIES / 200)) ]; then
    echo "  WARNING: the tar holds noticeably fewer entries than the car listed: check $ERR"
fi
{
    echo "host       $HU"
    echo "firmware   $VERSION"
    echo "profile    $PROFILE"
    echo "date       $STAMP"
    echo "tar        $TAR"
    echo "sha256     $SHA"
    echo "size       $size bytes"
    echo "entries    car $ENTRIES, tar $TAR_ENTRIES"
    echo "skipped    $(echo $SKIPPED)"
} >"$INFO"
if [ -s "$ERR" ]; then
    echo "  messages from tar/ssh ($ERR):"
    sed 's/^/    /' "$ERR" | head -n 20
fi

if [ "$EXTRACT" -ne 1 ]; then
    echo "Done (not extracted). Details: $INFO"
    exit 0
fi

# ---- 4. extract onto a case-sensitive volume --------------------------------------------------------------------------
IMG="$DUMP/hurootfs.sparseimage"
VOL="/Volumes/hurootfs"
if [ ! -e "$IMG" ]; then
    echo "Creating the case-sensitive image $IMG"
    hdiutil create -quiet -size 16g -type SPARSE -fs 'Case-sensitive APFS' -volname hurootfs "$DUMP/hurootfs" ||
        die "hdiutil create failed"
fi
if [ ! -d "$VOL" ]; then
    hdiutil attach -quiet "$IMG" || die "hdiutil attach failed"
fi
probe="$VOL/.case-probe-$$"
touch "$probe" || die "$VOL is not writable"
if [ -e "$VOL/.CASE-PROBE-$$" ]; then
    rm -f "$probe"
    die "$VOL is not case-sensitive: another volume has that name, eject it first"
fi
rm -f "$probe"

DEST="$VOL/rootfs-$VERSION"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    DEST="$VOL/rootfs-$VERSION-$STAMP"
fi
mkdir -p "$DEST"
echo "Extracting to $DEST"
tar -xpf "$TAR" -C "$DEST" 2>>"$ERR" || echo "  WARNING: tar reported problems while extracting, see $ERR"

echo "Making absolute symlinks relative..."
read -r -d '' FIX_SYMLINKS <<'PY'
import os
import sys

root = sys.argv[1]
fixed = 0
for folder, dirs, files in os.walk(root):
    for name in dirs + files:
        path = os.path.join(folder, name)
        if os.path.islink(path):
            target = os.readlink(path)
            if target.startswith("/"):
                os.unlink(path)
                os.symlink(os.path.relpath(root + target, folder), path)
                fixed += 1
print(fixed)
PY
FIXED=$(python3 -I -c "$FIX_SYMLINKS" "$DEST") || die "symlink fix failed"
echo "  $FIXED symlinks fixed"

ln -sfn "$DEST" "$VOL/rootfs"
mkdir -p "$HOME/entrynav2"
if [ -L "$HOME/entrynav2/rootfs" ] || [ ! -e "$HOME/entrynav2/rootfs" ]; then
    ln -sfn "$DEST" "$HOME/entrynav2/rootfs"
    LINKED="~/entrynav2/rootfs -> $DEST"
else
    LINKED="~/entrynav2/rootfs exists and is not a link: left alone"
fi
{
    echo "extracted  $DEST"
    echo "symlinks   $FIXED made relative"
    echo "linked     $VOL/rootfs, $LINKED"
} >>"$INFO"

echo
echo "Done."
echo "  copy      $DEST"
echo "  links     $VOL/rootfs; $LINKED"
echo "  details   $INFO"
echo "Build with: HU_ROOTFS=$DEST bash toolchain/tc.sh make ...   (from the repo)"
echo "After a reboot: hdiutil attach $IMG"
