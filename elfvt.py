"""Minimal ELF32 ARM reader: resolve the slots of a vtable symbol through dynamic relocations.

Usage: elfvt.py <lib.so> <vtable symbol> [<vtable symbol> ...]
       elfvt.py <lib.so> --sym <regex>      list dynamic symbols (addr, size, name)
"""

import re
import struct
import sys


def load(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1, "ELF32 LE only"
    (e_shoff,) = struct.unpack_from("<I", data, 0x20)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2E)
    secs = []
    for i in range(e_shnum):
        f = struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_shentsize)
        secs.append(dict(name=f[0], type=f[1], addr=f[3], off=f[4], size=f[5], link=f[6], entsize=f[9]))
    shstr = secs[e_shstrndx]

    def sname(s):
        o = shstr["off"] + s["name"]
        return data[o : data.index(b"\0", o)].decode()

    for s in secs:
        s["sname"] = sname(s)
    return data, secs


def cstr(data, off):
    return data[off : data.index(b"\0", off)].decode("latin1")


def dynsyms(data, secs):
    dsym = next(s for s in secs if s["sname"] == ".dynsym")
    dstr = secs[dsym["link"]]
    out = []
    for i in range(dsym["size"] // 16):
        name, value, size, info, other, shndx = struct.unpack_from("<IIIBBH", data, dsym["off"] + i * 16)
        out.append((cstr(data, dstr["off"] + name), value, size, shndx))
    return out


def vaddr_to_off(secs, addr):
    for s in secs:
        if s["type"] != 8 and s["addr"] and s["addr"] <= addr < s["addr"] + s["size"]:  # not NOBITS
            return s["off"] + addr - s["addr"]
    return None


def main():
    path = sys.argv[1]
    data, secs = load(path)
    syms = dynsyms(data, secs)
    if sys.argv[2] == "--sym":
        rx = re.compile(sys.argv[3])
        for name, value, size, shndx in syms:
            if rx.search(name):
                print(f"{value:08x} {size:5d} {'U' if shndx == 0 else 'D'} {name}")
        return
    by_addr = {}
    for name, value, size, shndx in syms:
        if shndx and value:
            by_addr.setdefault(value & ~1, []).append(name)
    relocs = {}
    for s in secs:
        if s["type"] == 9:  # SHT_REL
            for i in range(s["size"] // 8):
                r_off, r_info = struct.unpack_from("<II", data, s["off"] + i * 8)
                relocs[r_off] = (r_info & 0xFF, r_info >> 8)
    for want in sys.argv[2:]:
        hit = [(v, sz) for n, v, sz, sh in syms if n == want and sh]
        if not hit:
            print(f"{want}: not defined here")
            continue
        value, size = hit[0]
        print(f"{want}: at {value:08x}, {size} bytes = {size // 4} words (2 header + {size // 4 - 2} slots)")
        off = vaddr_to_off(secs, value)
        for w in range(size // 4):
            addr = value + 4 * w
            raw = struct.unpack_from("<I", data, off + 4 * w)[0]
            kind, symidx = relocs.get(addr, (None, None))
            if kind == 2:  # R_ARM_ABS32 -> symbol
                target = syms[symidx][0]
            elif kind == 23:  # R_ARM_RELATIVE -> address in place
                target = ",".join(by_addr.get(raw & ~1, [f"local {raw:08x}"]))
            elif raw == 0:
                target = "0"
            else:
                target = f"raw {raw:08x}"
            label = "offset-to-top" if w == 0 else "typeinfo" if w == 1 else f"slot {w - 2}"
            print(f"  {label:>14}: {target}")


if __name__ == "__main__":
    main()
