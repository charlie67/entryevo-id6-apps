"""Read an EntryNav2 iDrive text database (/opt/hmi/data/ro/<brand>/db/text.db). Read-only.

Format, as found on firmware 202402191339:
  header   magic de ca fb ad, then (from 0x20) big-endian u32 offsets of 24-byte index records, 0-terminated
  record   u32 0x22000001, u32 chunk offset, u32 0xdeadbeef, u32 0, u32 0xffffffff, u32 timestamp
  chunk    u32 BE 0x00000001, u32 BE length of what follows, u32 LE uncompressed size, then UCL NRV2D (8-bit)
           data. No checksum was found in the chunk or its index record.
  text     UTF-16LE with BOM, one "id<TAB>text" per line; one chunk per language

Usage:
  python3 -I textdb.py <text.db> list                     chunks: index, offset, size, first texts
  python3 -I textdb.py <text.db> grep <regex> [chunk]     search texts (all chunks, or one)
  python3 -I textdb.py <text.db> id <textId>              one text id in every chunk
  python3 -I textdb.py <text.db> dump <chunk> <out.txt>   write a chunk as UTF-8 "id<TAB>text" lines
"""

import re
import struct
import sys


def nrv2d_8(src, ilen, out_size):
    """UCL NRV2D decompression, 8-bit bit buffer."""
    dst = bytearray()
    bb = 0
    last_m_off = 1

    def getbit():
        nonlocal bb, ilen
        if bb & 0x7F:
            bb *= 2
        else:
            bb = src[ilen] * 2 + 1
            ilen += 1
        return (bb >> 8) & 1

    while len(dst) < out_size:
        while getbit():
            dst.append(src[ilen])
            ilen += 1
        m_off = 1
        while True:
            m_off = m_off * 2 + getbit()
            if getbit():
                break
            m_off = (m_off - 1) * 2 + getbit()
        if m_off == 2:
            m_off = last_m_off
            m_len = getbit()
        else:
            m_off = ((m_off - 3) * 256 + src[ilen]) & 0xFFFFFFFF
            ilen += 1
            if m_off == 0xFFFFFFFF:
                break
            m_len = (m_off ^ 0xFFFFFFFF) & 1
            m_off = (m_off >> 1) + 1
            last_m_off = m_off
        m_len = m_len * 2 + getbit()
        if m_len == 0:
            m_len = 1
            while True:
                m_len = m_len * 2 + getbit()
                if getbit():
                    break
            m_len += 2
        m_len += 1 if m_off > 0x500 else 0
        if m_off > len(dst):
            raise ValueError(f"bad match offset {m_off} at output {len(dst)}")
        for _ in range(m_len + 1):
            dst.append(dst[-m_off])
    return bytes(dst)


def chunks(data):
    assert data[:4] == b"\xde\xca\xfb\xad", "not a text.db (magic de ca fb ad)"
    pos = 0x20
    while True:
        (rec,) = struct.unpack_from(">I", data, pos)
        pos += 4
        if rec == 0:
            break
        tag, off = struct.unpack_from(">II", data, rec)
        yield tag, off


def decode(data, off):
    _one, _length = struct.unpack_from(">II", data, off)
    (size,) = struct.unpack_from("<I", data, off + 8)
    raw = nrv2d_8(data, off + 12, size)
    text = raw.decode("utf-16-le", "replace").lstrip("﻿")
    table = {}
    for line in text.split("\n"):
        if "\t" in line:
            key, value = line.split("\t", 1)
            table[key] = value
    return size, table


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    data = open(sys.argv[1], "rb").read()
    cmd = sys.argv[2]
    found = list(chunks(data))
    if cmd == "list":
        for n, (tag, off) in enumerate(found):
            size, table = decode(data, off)
            sample = " | ".join(table.get(k, "") for k in ("3008", "3016", "3024"))
            print(f"{n:2d}  offset {off:#09x}  {size:7d} bytes  {len(table):5d} texts  {sample}")
    elif cmd == "grep":
        rx = re.compile(sys.argv[3], re.I)
        which = [int(sys.argv[4])] if len(sys.argv) > 4 else range(len(found))
        for n in which:
            _, table = decode(data, found[n][1])
            for key, value in table.items():
                if rx.search(value):
                    print(f"chunk {n:2d}  {key:>7}  {value}")
    elif cmd == "id":
        for n, (_, off) in enumerate(found):
            _, table = decode(data, off)
            print(f"chunk {n:2d}  {table.get(sys.argv[3], '(missing)')}")
    elif cmd == "dump":
        _, table = decode(data, found[int(sys.argv[3])][1])
        with open(sys.argv[4], "w", encoding="utf-8") as f:
            for key, value in table.items():
                f.write(f"{key}\t{value}\n")
        print(f"wrote {len(table)} texts to {sys.argv[4]}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
