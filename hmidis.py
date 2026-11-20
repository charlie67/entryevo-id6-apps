"""Disassembly/analysis helper for the (dynsym-symbolised) HmiMain3D ARM executable.

Although HmiMain3D is '.symtab'-stripped, its .dynsym keeps ~318k defined C++
symbols, so we can resolve addresses <-> names across the whole binary.

Needs: capstone + pyelftools (pip install capstone pyelftools, e.g. in a venv).
ARM note: a function symbol value with the low bit set is Thumb; real entry = value & ~1.

Usage (run with `python3 -I hmidis.py <HmiMain3D> <cmd> ...`):
  sym     <regex>                 list matching defined symbols (addr size type name)
  dis     <name|0xaddr> [nbytes]  disassemble a function (ARM/Thumb auto, resolved targets)
  win     <0xaddr> [ctx]          disassemble ctx instrs around an addr, in its function
  str     <regex> [limit]         list .rodata strings matching regex (vaddr + text)
  xref    <0xaddr> [...]          find LE-word refs to vaddr(s) across the image (data + literal pools)
  callers <name|0xaddr> [...]     find bl/blx/b call sites of function(s), with preceding context
  deref   <0xaddr>                show symbol/string/section an address lands in

ARM note: a function symbol value with the low bit set is Thumb; real entry = value & ~1.
"""
import re, sys, struct, bisect
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC, ARM_INS_LDR, ARM_INS_MOVW, ARM_INS_MOVT


class Elf:
    def __init__(self, path):
        self.f = ELFFile(open(path, "rb"))
        self.data = self.f.stream
        self.segs = [(s['p_vaddr'], s['p_offset'], s['p_filesz'])
                     for s in self.f.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.secs = [(s.name, s['sh_addr'], s['sh_offset'], s['sh_size'], s['sh_type'])
                     for s in self.f.iter_sections() if s['sh_addr']]
        # symbols
        ds = self.f.get_section_by_name('.dynsym')
        self.by_addr = {}          # clean addr -> name (first wins = usually the function)
        self.func_starts = {}      # clean addr -> (name, thumb, size)
        self.name2 = {}            # name -> (value, size, type)
        for sym in ds.iter_symbols():
            if sym['st_shndx'] == 'SHN_UNDEF' or not sym['st_value']:
                continue
            v = sym['st_value']; t = sym['st_info']['type']; n = sym.name; sz = sym['st_size']
            clean = v & ~1
            self.name2.setdefault(n, (v, sz, t))
            if t == 'STT_FUNC':
                self.func_starts.setdefault(clean, (n, v & 1, sz))
            self.by_addr.setdefault(clean, n)
        self.sorted_addrs = sorted(self.by_addr)
        self.md_a = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
        self.md_t = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
        for md in (self.md_a, self.md_t):
            md.detail = True

    def off(self, vaddr):
        for va, of, sz in self.segs:
            if va <= vaddr < va + sz:
                return of + (vaddr - va)
        return None

    def read(self, vaddr, n):
        o = self.off(vaddr)
        if o is None:
            return None
        self.data.seek(o); return self.data.read(n)

    def f2v(self, off):
        """file offset -> vaddr (inverse of off())"""
        for va, of, sz in self.segs:
            if of <= off < of + sz:
                return va + (off - of)
        return None

    def sec_of(self, vaddr):
        for name, addr, of, sz, ty in self.secs:
            if addr <= vaddr < addr + sz:
                return name
        return None

    def nearest(self, vaddr):
        """symbol at-or-before vaddr -> (name, delta)"""
        clean = vaddr & ~1
        i = bisect.bisect_right(self.sorted_addrs, clean) - 1
        if i < 0:
            return None, None
        a = self.sorted_addrs[i]
        return self.by_addr[a], clean - a

    def cstr(self, vaddr, maxlen=200):
        b = self.read(vaddr, maxlen)
        if b is None:
            return None
        z = b.find(b'\0')
        s = b[:z if z >= 0 else maxlen]
        try:
            txt = s.decode('utf-8')
        except UnicodeDecodeError:
            return None
        if z < 0 or not all(32 <= ord(c) < 127 or c in '\t' for c in txt):
            return None
        return txt

    def deref(self, vaddr):
        """Describe what an address points to: symbol+delta, string, or section."""
        n, d = self.nearest(vaddr)
        if n is not None and d is not None and d < 0x4000:
            tag = n if d == 0 else f"{n}+{d:#x}"
            return tag
        s = self.cstr(vaddr)
        if s is not None:
            return f'"{s}"'
        sec = self.sec_of(vaddr)
        return f"<{sec}:{vaddr:#x}>" if sec else f"{vaddr:#x}"


def disfunc(e, start, size, thumb):
    md = e.md_t if thumb else e.md_a
    code = e.read(start, size)
    pend = {}  # reg -> (movw_imm, addr_of_pending) for movw/movt pairing
    out = []
    for ins in md.disasm(code, start):
        line = f"  {ins.address:#010x}  {ins.mnemonic:<8} {ins.op_str}"
        ann = []
        # branch/imm targets -> symbol
        if ins.id and ins.operands:
            for op in ins.operands:
                if op.type == ARM_OP_IMM and ins.mnemonic[0] in ('b', 'c') and abs(op.imm) > 0x1000:
                    n, d = e.nearest(op.imm)
                    if n is not None and d is not None and d < 0x2000:
                        ann.append(n if d == 0 else f"{n}+{d:#x}")
        # pc-relative literal load
        if ins.id == ARM_INS_LDR and ins.operands and ins.operands[-1].type == ARM_OP_MEM \
                and ins.operands[-1].mem.base == ARM_REG_PC:
            pc = (ins.address + (4 if thumb else 8)) & ~3
            lit = pc + ins.operands[-1].mem.disp
            w = e.read(lit, 4)
            if w and len(w) == 4:
                val = struct.unpack('<I', w)[0]
                ann.append(f"={val:#x} {e.deref(val)}")
        # movw/movt immediate pair -> absolute pointer
        if ins.id == ARM_INS_MOVW and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
            pend[ins.operands[0].reg] = ins.operands[1].imm
        elif ins.id == ARM_INS_MOVT and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
            r = ins.operands[0].reg
            if r in pend:
                val = pend.pop(r) | (ins.operands[1].imm << 16)
                ann.append(f"=>{val:#x} {e.deref(val)}")
        if ann:
            line = f"{line:<52} ; " + " | ".join(ann)
        out.append(line)
    return out


def main():
    e = Elf(sys.argv[1]); cmd = sys.argv[2]
    if cmd == 'sym':
        rx = re.compile(sys.argv[3])
        rows = [(v, sz, t, n) for n, (v, sz, t) in e.name2.items() if rx.search(n)]
        for v, sz, t, n in sorted(rows):
            print(f"{v:#010x} sz={sz:<6} {t[4]} {n}")
        print(f"-- {len(rows)} match", file=sys.stderr)
    elif cmd == 'dis':
        tgt = sys.argv[3]
        if tgt.startswith('0x'):
            addr = int(tgt, 16); clean = addr & ~1
            name, thumb, size = e.func_starts.get(clean, (e.by_addr.get(clean, '?'), addr & 1, 0))
        else:
            v, size, t = e.name2[tgt]; clean = v & ~1; thumb = v & 1; name = tgt
        size = int(sys.argv[4], 0) if len(sys.argv) > 4 else (size or 256)
        print(f"{name}  @ {clean:#x}  {'THUMB' if thumb else 'ARM'}  {size} bytes")
        for l in disfunc(e, clean, size, thumb):
            print(l)
    elif cmd == 'str':
        rx = re.compile(sys.argv[3])
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 80
        ro = e.f.get_section_by_name('.rodata')
        base = ro['sh_addr']; blob = ro.data(); n = 0
        for m in re.finditer(rb'[\x20-\x7e]{4,}', blob):
            s = m.group().decode()
            if rx.search(s):
                print(f"{base + m.start():#010x}  {s}")
                n += 1
                if n >= limit:
                    break
    elif cmd == 'win':
        addr = int(sys.argv[3], 16); ctx = int(sys.argv[4]) if len(sys.argv) > 4 else 14
        fs = sorted(e.func_starts)
        start = fs[bisect.bisect_right(fs, addr & ~1) - 1]
        name, thumb, size = e.func_starts[start]
        if not size:
            i = fs.index(start); size = (fs[i + 1] - start) if i + 1 < len(fs) else 0x200
        print(f"// in {name} @ {start:#x} ({'T' if thumb else 'A'}) size {size}")
        lines = disfunc(e, start, size, thumb)
        if lines:
            best = min(range(len(lines)), key=lambda k: abs(int(lines[k].split()[0], 16) - addr))
            for k in range(max(0, best - ctx), min(len(lines), best + ctx + 1)):
                print((">>" if k == best else "  ") + lines[k])
    elif cmd == 'xref':
        blob = open(sys.argv[1], 'rb').read()
        for tgt in sys.argv[3:]:
            va = int(tgt, 16); needle = struct.pack('<I', va)
            occ = [m.start() for m in re.finditer(re.escape(needle), blob)]
            print(f"\n== refs to {va:#x} ({e.deref(va)}): {len(occ)} ==")
            for o in occ[:60]:
                v = e.f2v(o)
                if v is None:
                    print(f"  file@{o:#x} (unmapped)"); continue
                n, d = e.nearest(v)
                where = f"{n}+{d:#x}" if n and d is not None and d < 0x40000 else ""
                print(f"  {v:#010x} [{e.sec_of(v)}] {where}")
    elif cmd == 'callers':
        targets = {(int(a, 16) if a.startswith('0x') else e.name2[a][0]) & ~1 for a in sys.argv[3:]}
        fs = sorted(e.func_starts); hits = []
        for i, start in enumerate(fs):
            name, thumb, size = e.func_starts[start]
            if not size:
                size = min((fs[i + 1] - start) if i + 1 < len(fs) else 0x100, 0x2000)
            code = e.read(start, size)
            if not code:
                continue
            md = e.md_t if thumb else e.md_a
            for ins in md.disasm(code, start):
                if ins.mnemonic[0] == 'b' and ins.operands and ins.operands[-1].type == ARM_OP_IMM \
                        and (ins.operands[-1].imm & ~1) in targets:
                    hits.append((ins.address, name, start, thumb, ins.operands[-1].imm & ~1))
        print(f"{len(hits)} call site(s)")
        for addr, name, start, thumb, tgt in hits:
            print(f"\n# {addr:#x} in {name}  ->  {e.by_addr.get(tgt, '?')}")
            md = e.md_t if thumb else e.md_a
            lo = max(start, addr - 40); code = e.read(lo, addr - lo + 4)
            for ins in md.disasm(code, lo):
                imm = f"  (#{ins.operands[-1].imm:#x})" if ins.operands and ins.operands[-1].type == ARM_OP_IMM else ''
                print(f"    {ins.address:#010x}  {ins.mnemonic:<8} {ins.op_str}{imm}")
                if ins.address >= addr:
                    break
    elif cmd == 'deref':
        print(e.deref(int(sys.argv[3], 16)))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
