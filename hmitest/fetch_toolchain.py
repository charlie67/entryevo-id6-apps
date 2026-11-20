#!/usr/bin/env python3
"""Fetch the exact GCC-4.7.2 / eglibc-2.15 armhf cross toolchain the EntryEVO head unit was built
with, from the Ubuntu 12.10 (quantal) archive on old-releases.ubuntu.com, and extract it to /opt/tc.

No apt/debootstrap: it reads the quantal Packages index, resolves the toolchain closure, downloads
the .debs, and `dpkg -x` unpacks them. Run at image-build time (see Dockerfile).
"""
import os, re, subprocess, sys, urllib.request

BASE = "http://old-releases.ubuntu.com/ubuntu"
SEEDS = ["gcc-4.7-arm-linux-gnueabihf", "g++-4.7-arm-linux-gnueabihf",
         "binutils-arm-linux-gnueabihf", "libmpfr4", "libmpc2"]
DEST = "/opt/tc"


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def load_index():
    import gzip
    pkgs = {}
    for comp in ("main", "universe"):
        raw = gzip.decompress(fetch(f"{BASE}/dists/quantal/{comp}/binary-amd64/Packages.gz"))
        for block in raw.decode("utf-8", "replace").split("\n\n"):
            d = {}
            for line in block.split("\n"):
                if line[:1] in (" ", "\t") or ":" not in line:
                    continue
                k, _, v = line.partition(":")
                d[k.strip()] = v.strip()
            n = d.get("Package")
            if n:
                pkgs.setdefault(n, {"fn": d.get("Filename"), "dep": d.get("Depends", "")})
    return pkgs


def first_alts(depends):
    out = []
    for clause in depends.split(","):
        m = re.match(r"\s*([a-z0-9.+-]+)", clause.split("|")[0])
        if m:
            out.append(m.group(1))
    return out


def relevant(n):
    return "arm-linux-gnueabihf" in n or "armhf-cross" in n or n in ("libmpfr4", "libmpc2")


def main():
    pkgs = load_index()
    seen, stack = set(), list(SEEDS)
    while stack:
        n = stack.pop()
        if n in seen or n not in pkgs:
            continue
        seen.add(n)
        for dd in first_alts(pkgs[n]["dep"]):
            if dd not in seen and relevant(dd):
                stack.append(dd)
    print(f"resolved {len(seen)} packages: {', '.join(sorted(seen))}", flush=True)
    os.makedirs("/tmp/debs", exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    for n in sorted(seen):
        fn = pkgs[n]["fn"]
        if not fn:
            print("  !! no Filename for", n); continue
        deb = f"/tmp/debs/{os.path.basename(fn)}"
        with open(deb, "wb") as f:
            f.write(fetch(f"{BASE}/{fn}"))
        subprocess.check_call(["dpkg", "-x", deb, DEST])
    # sanity: the compiler must be present
    gpp = os.path.join(DEST, "usr/bin/arm-linux-gnueabihf-g++-4.7")
    if not os.path.exists(gpp):
        sys.exit("FATAL: compiler not extracted")
    print("toolchain extracted to", DEST, flush=True)


if __name__ == "__main__":
    main()
