#!/usr/bin/env python3
# Copyright (c) 2026 Charlie Robinson
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
"""Build the install archive: artifacts/helloplugin-armhf.tar, ready to copy to the head unit.

Its files sit at the paths they take on the car (opt/hmi/data/ro/Plugins/HelloPlugin/...), with an MD5SUMS file
the car's BusyBox can check before and after the copy. The archive is reproducible: fixed owner, modes and dates.
Run make_db.py first (or let this script run it); libHelloPlugin.so must already be built (see the Makefile).

Usage: package.py
"""

import subprocess
import sys
import tarfile
import time
from hashlib import md5
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGIN = "opt/hmi/data/ro/Plugins/HelloPlugin"
PLUGIN_FILES = (
    "libHelloPlugin.so",
    "HelloPlugin.manifest",
    "HelloPlugin.xml",
    "HelloPlugin_ALL_Texts.zip",
    "HelloPlugin_ALL_Images.zip",
)
FIXED = int(time.mktime((2026, 11, 20, 0, 0, 0, 0, 0, 0)))


def build_files() -> dict:
    subprocess.run([sys.executable, "-I", str(ROOT / "make_db.py"), str(ROOT)], check=True)
    files = {}
    for name in PLUGIN_FILES:
        data = (ROOT / name).read_bytes()
        files[f"{PLUGIN}/{name}"] = data
    so = files[f"{PLUGIN}/libHelloPlugin.so"]
    if not so.startswith(b"\x7fELF"):
        raise SystemExit("FAIL: libHelloPlugin.so is not an ARM ELF (build it with the Makefile first)")
    files["MD5SUMS"] = "".join(
        f"{md5(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    for doc in ("INSTALL.md", "README.md"):
        p = ROOT / doc
        if p.is_file():
            files[doc] = p.read_bytes()
    return files


def add(tar: tarfile.TarFile, name: str, data: bytes, mode: int):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.mtime = FIXED
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    tar.addfile(info, BytesIO(data))


def main():
    files = build_files()
    out_dir = ROOT / "artifacts"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "helloplugin-armhf.tar"
    executables = {f"{PLUGIN}/libHelloPlugin.so"}
    with tarfile.open(out, "w") as tar:
        for name in sorted(files):
            mode = 0o755 if name in executables else 0o644
            add(tar, name, files[name], mode)
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(files)} files)")


if __name__ == "__main__":
    main()
