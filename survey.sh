#!/bin/bash
# survey.sh: read-only survey of an EntryNav2 head unit, run from the Mac over SSH (ENET cable).
# It finds what a copy of the car's system needs (sizes, mounts, library folders, plugin folders) before dumping it.
# Nothing is written on the car, not even in /tmp: the commands below only read, and their output comes back over SSH.
#
#   ./survey.sh                     # root@169.254.1.0, the install guide's address
#   ./survey.sh root@192.168.0.10   # another address
#
# Output: hu-survey-<date>.txt next to this script, with a summary computed on the Mac at the end.
set -u

HU="${1:-root@169.254.1.0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DIR/hu-survey-$(date +%Y%m%d-%H%M%S).txt"

echo "Surveying $HU (read-only) -> $OUT"

# Everything between the REMOTE markers runs on the car, under BusyBox sh. Quoted marker: nothing expands on the Mac.
if ! ssh -o ConnectTimeout=10 "$HU" 'sh -s' >"$OUT" 2>&1 <<'REMOTE'; then
L=/usr/local/lib:/opt/hmi/lib:/usr/lib:/lib
section() { echo; echo "== $*"; }

section "version"
head -n 1 /etc/version
uname -a

section "mounts"
mount

section "free space (KiB)"
df -k

section "top-level sizes (KiB)"
for d in /bin /sbin /lib /usr /etc /opt/* /var/local/*; do
    [ -e "$d" ] && du -sk "$d" 2>/dev/null
done

section "/usr and /opt/hmi breakdown (KiB)"
for d in /usr/* /opt/hmi/*; do
    [ -e "$d" ] && du -sk "$d" 2>/dev/null
done

section "default dump set (KiB)"
cd / && for d in bin sbin lib usr etc opt/hmi; do
    [ -e "$d" ] && du -sk "$d" 2>/dev/null
done

section "entries in default dump set"
cd / && find bin sbin lib usr etc opt/hmi 2>/dev/null | wc -l

section "HmiMain3D"
H=$(find /opt /usr -name HmiMain3D -type f 2>/dev/null | head -n 1)
echo "${H:-not found}"

section "libraries HmiMain3D loads (traced by the loader, not executed)"
if [ -n "$H" ]; then
    LD_TRACE_LOADED_OBJECTS=1 LD_LIBRARY_PATH=$L /lib/ld-linux-armhf.so.3 "$H" 2>&1
fi

section "plugin roots"
ls -la /opt/hmi/data/ro /opt/hmi/data/ro/Plugins* /var/local/data/HMI/Plugins 2>&1

section "plugin manifests and text databases"
find /opt /var/local/data/HMI \( -name '*.manifest' -o -name '*_ALL_Texts.zip' \) 2>/dev/null

section "BMW framework libraries"
find /lib /usr /opt -name 'lib*Framework*.so*' 2>/dev/null

section "absolute symlinks in library folders (first 20)"
for d in /lib /usr/lib /usr/local/lib /opt/hmi/lib; do
    find "$d" -type l 2>/dev/null
done | while read -r l; do
    t=$(readlink "$l")
    case "$t" in /*) echo "$l -> $t" ;; esac
done | head -n 20

exit 0
REMOTE
    echo "FAIL: ssh to $HU failed, see $OUT" >&2
    exit 1
fi

# ---- summary, computed on the Mac from what came back ----------------------------------------------------------------
section_of() {  # the lines of one "== <title>" section
    awk -v t="== $1" 'index($0, t) == 1 { f = 1; next } /^== / { f = 0 } f' "$OUT"
}

{
    echo
    echo "== summary (computed on the Mac)"
    kib=$(section_of "default dump set" | awk '$1 ~ /^[0-9]+$/ { s += $1 } END { print s + 0 }')
    echo "default dump set (bin sbin lib usr etc opt/hmi): $((kib / 1024)) MiB, $(section_of "entries in default dump set" | tr -d ' \n') entries"

    libs=$(section_of "libraries HmiMain3D loads" | awk '/=> \// { print $3 }')
    if [ -z "$libs" ]; then
        echo "library folders HmiMain3D uses: none found (see the HmiMain3D sections above)"
    else
        echo "library folders HmiMain3D uses:"
        for d in $(printf '%s\n' $libs | xargs -n 1 dirname | sort -u); do
            case "$d" in
                /bin | /bin/* | /sbin | /sbin/* | /lib | /lib/* | /usr | /usr/* | /etc | /etc/* | /opt/hmi | /opt/hmi/*)
                    echo "  $d  (in the default dump)" ;;
                *)
                    echo "  $d  NOT in the default dump: add ${d#/} to the tar list" ;;
            esac
        done
    fi

    missing=$(section_of "libraries HmiMain3D loads" | grep -c 'not found')
    echo "libraries the loader could not find: $missing"
    echo
    echo "Before dumping, check in the sections above: separate mounts under /opt, and any folder in the GB range."
} | tee -a "$OUT"

echo
echo "Full survey: $OUT"
