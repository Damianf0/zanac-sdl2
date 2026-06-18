#!/usr/bin/env python3
"""Desensamblador Z80 con descenso recursivo para ROMs de cartucho MSX.

Sigue el entry point (INIT del header AB) y todos los destinos de CALL/JP/JR
(incl. condicionales) marcando bytes alcanzables como CODIGO; el resto queda
como DATA (DB). Emite un .asm con direcciones, bytes y mnemónicos en el mismo
formato anotado que usamos en The Castle (sub_XXXX, etiquetas, BIOS).

El decodificador de opcodes se valida contra el desensamblador de openMSX
(tools/dis_oracle.tcl + check_dis.py).

Uso:  python tools/z80dis.py zanac.rom zanac_disasm.asm [--org 0x4000]
"""
import sys

# ===========================================================================
# Tablas de registros / condiciones
# ===========================================================================
R   = ['B', 'C', 'D', 'E', 'H', 'L', '(HL)', 'A']
RP  = ['BC', 'DE', 'HL', 'SP']
RP2 = ['BC', 'DE', 'HL', 'AF']
CC  = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
ALU = ['ADD A,', 'ADC A,', 'SUB ', 'SBC A,', 'AND ', 'XOR ', 'OR ', 'CP ']
ROT = ['RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SLL', 'SRL']

# Símbolos BIOS MSX más comunes (se anotan en las llamadas absolutas)
BIOS = {
    0x0000: 'RST0', 0x0008: 'SYNCHR', 0x000C: 'RDSLT', 0x0014: 'WRSLT',
    0x001C: 'CALSLT', 0x0024: 'ENASLT', 0x0030: 'CALLF',
    0x0038: 'KEYINT', 0x0041: 'DISSCR', 0x0044: 'ENASCR', 0x0047: 'WRTVDP',
    0x004A: 'RDVRM', 0x004D: 'WRTVRM', 0x0050: 'SETRD', 0x0053: 'SETWRT',
    0x0056: 'FILVRM', 0x0059: 'LDIRMV', 0x005C: 'LDIRVM', 0x005F: 'CHGMOD',
    0x0062: 'CHGCLR', 0x0069: 'CLRSPR', 0x006D: 'INITXT', 0x0070: 'INIT32',
    0x0073: 'INIGRP', 0x0076: 'INIMLT', 0x0079: 'SETTXT', 0x007C: 'SETT32',
    0x007F: 'SETGRP', 0x0082: 'SETMLT', 0x0085: 'CALPAT', 0x0088: 'CALATR',
    0x008B: 'GSPSIZ', 0x008E: 'GRPPRT', 0x0090: 'GICINI', 0x0093: 'WRTPSG',
    0x0096: 'RDPSG', 0x0099: 'STRTMS', 0x009C: 'CHSNS', 0x009F: 'CHGET',
    0x00A2: 'CHPUT', 0x00A5: 'LPTOUT', 0x00A8: 'LPTSTT', 0x00AB: 'CNVCHR',
    0x00C0: 'BEEP', 0x00C3: 'CLS', 0x00C6: 'POSIT', 0x00CC: 'ERAFNK',
    0x00CF: 'DSPFNK', 0x00D2: 'TOTEXT', 0x00D5: 'GTSTCK', 0x00D8: 'GTTRIG',
    0x00DB: 'GTPAD', 0x00DE: 'GTPDL', 0x00E1: 'TAPION', 0x0138: 'RSLREG',
    0x013B: 'WSLREG', 0x013E: 'RDVDP', 0x0141: 'SNSMAT', 0x0144: 'PHYDIO',
}

def lo(b): return b & 0xFF


class Disasm:
    def __init__(self, rom, org):
        self.rom = rom
        self.org = org
        self.end = org + len(rom)
        self.code = bytearray(len(rom))   # 1 = inicio de instrucción de código
        self.label = {}                   # addr -> nombre de etiqueta
        self.insns = {}                   # addr -> (length, text, target)

    def rb(self, a):
        return self.rom[a - self.org] if self.org <= a < self.end else 0

    def rw(self, a):
        return self.rb(a) | (self.rb(a + 1) << 8)

    def inside(self, a):
        return self.org <= a < self.end

    # -- decodifica UNA instrucción en addr -> (length, text, [targets], is_terminal)
    def decode(self, a):
        b = self.rb(a)
        if b == 0xCB:   return self._cb(a)
        if b == 0xED:   return self._ed(a)
        if b in (0xDD, 0xFD): return self._ix(a, 'IX' if b == 0xDD else 'IY')
        return self._main(a, b)

    def _imm8(self, a):  return self.rb(a)
    def _imm16(self, a): return self.rw(a)

    def _main(self, a, b):
        x, y, z = b >> 6, (b >> 3) & 7, b & 7
        p, q = y >> 1, y & 1
        nn = self._imm16(a + 1)
        n = self._imm8(a + 1)
        d = self.rb(a + 1)
        rel = (a + 2 + (d - 256 if d > 127 else d)) & 0xFFFF
        T = []          # targets de control de flujo
        term = False    # fin de bloque lineal (RET/JP incondicional/JR)

        if x == 0:
            if b == 0x00: return (1, 'NOP', T, term)
            if b == 0x08: return (1, "EX AF,AF'", T, term)
            if b == 0x10: T.append(rel); return (2, f'DJNZ {{{rel:04X}}}', T, term)
            if b == 0x18: T.append(rel); return (2, f'JR {{{rel:04X}}}', T, True)
            if b in (0x20, 0x28, 0x30, 0x38):
                T.append(rel); return (2, f'JR {CC[y-4]},{{{rel:04X}}}', T, term)
            if z == 1:
                if q == 0: return (3, f'LD {RP[p]},{nn:#06x}', T, term)
                return (1, f'ADD HL,{RP[p]}', T, term)
            if z == 2:
                tab = {0: 'LD (BC),A', 1: 'LD A,(BC)', 2: 'LD (DE),A',
                       3: 'LD A,(DE)'}
                if y < 4: return (1, tab[y], T, term)
                if y == 4: return (3, f'LD ({nn:#06x}),HL', T, term)
                if y == 5: return (3, f'LD HL,({nn:#06x})', T, term)
                if y == 6: return (3, f'LD ({nn:#06x}),A', T, term)
                return (3, f'LD A,({nn:#06x})', T, term)
            if z == 3:
                if q == 0: return (1, f'INC {RP[p]}', T, term)
                return (1, f'DEC {RP[p]}', T, term)
            if z == 4: return (1, f'INC {R[y]}', T, term)
            if z == 5: return (1, f'DEC {R[y]}', T, term)
            if z == 6: return (2, f'LD {R[y]},{n:#04x}', T, term)
            misc = ['RLCA', 'RRCA', 'RLA', 'RRA', 'DAA', 'CPL', 'SCF', 'CCF']
            return (1, misc[y], T, term)

        if x == 1:
            if b == 0x76: return (1, 'HALT', T, term)
            return (1, f'LD {R[y]},{R[z]}', T, term)

        if x == 2:
            return (1, f'{ALU[y]}{R[z]}', T, term)

        # x == 3
        if z == 0: return (1, f'RET {CC[y]}', T, term)
        if z == 1:
            if q == 0: return (1, f'POP {RP2[p]}', T, term)
            sp = ['RET', 'EXX', 'JP (HL)', 'LD SP,HL']
            term = p in (0, 2)   # RET / JP (HL) terminan el bloque
            return (1, sp[p], T, term)
        if z == 2:
            T.append(nn); return (3, f'JP {CC[y]},{{{nn:04X}}}', T, term)
        if z == 3:
            if y == 0: T.append(nn); return (3, f'JP {{{nn:04X}}}', T, True)
            if y == 2: return (2, f'OUT ({n:#04x}),A', T, term)
            if y == 3: return (2, f'IN A,({n:#04x})', T, term)
            if y == 4: return (1, 'EX (SP),HL', T, term)
            if y == 5: return (1, 'EX DE,HL', T, term)
            if y == 6: return (1, 'DI', T, term)
            return (1, 'EI', T, term)
        if z == 4:
            T.append(nn); return (3, f'CALL {CC[y]},{{{nn:04X}}}', T, term)
        if z == 5:
            if q == 0: return (1, f'PUSH {RP2[p]}', T, term)
            if p == 0: T.append(nn); return (3, f'CALL {{{nn:04X}}}', T, term)
            return (1, 'DB 0x%02X' % b, T, term)   # DD/ED/FD ya tratados
        if z == 6:
            return (2, f'{ALU[y]}{n:#04x}', T, term)
        # z == 7: RST
        tgt = y * 8
        T.append(tgt)
        return (1, f'RST {tgt:#04x}', T, term)

    def _cb(self, a):
        b = self.rb(a + 1)
        x, y, z = b >> 6, (b >> 3) & 7, b & 7
        if x == 0: return (2, f'{ROT[y]} {R[z]}', [], False)
        op = ['BIT', 'RES', 'SET'][x - 1]
        return (2, f'{op} {y},{R[z]}', [], False)

    def _ed(self, a):
        b = self.rb(a + 1)
        x, y, z = b >> 6, (b >> 3) & 7, b & 7
        p, q = y >> 1, y & 1
        nn = self._imm16(a + 2)
        if x == 1:
            if z == 0: return (2, f'IN {R[y]},(C)' if y != 6 else 'IN (C)', [], False)
            if z == 1: return (2, f'OUT (C),{R[y]}' if y != 6 else 'OUT (C),0', [], False)
            if z == 2:
                return (2, (f'SBC HL,{RP[p]}' if q == 0 else f'ADC HL,{RP[p]}'), [], False)
            if z == 3:
                if q == 0: return (4, f'LD ({nn:#06x}),{RP[p]}', [], False)
                return (4, f'LD {RP[p]},({nn:#06x})', [], False)
            if z == 4: return (2, 'NEG', [], False)
            if z == 5: return (2, 'RETN' if y == 0 else 'RETI', [], True)
            if z == 6:
                im = {0: '0', 1: '0/1', 2: '1', 3: '2', 4: '0', 5: '0/1', 6: '1', 7: '2'}
                return (2, f'IM {im[y]}', [], False)
            sp = {0: 'LD I,A', 1: 'LD R,A', 2: 'LD A,I', 3: 'LD A,R',
                  4: 'RRD', 5: 'RLD', 6: 'NOP', 7: 'NOP'}
            return (2, sp[y], [], False)
        if x == 2 and z < 4 and y >= 4:
            blk = {(4, 0): 'LDI', (5, 0): 'LDD', (6, 0): 'LDIR', (7, 0): 'LDDR',
                   (4, 1): 'CPI', (5, 1): 'CPD', (6, 1): 'CPIR', (7, 1): 'CPDR',
                   (4, 2): 'INI', (5, 2): 'IND', (6, 2): 'INIR', (7, 2): 'INDR',
                   (4, 3): 'OUTI', (5, 3): 'OUTD', (6, 3): 'OTIR', (7, 3): 'OTDR'}
            return (2, blk[(y, z)], [], False)
        return (2, f'DB 0xED,0x{b:02X}', [], False)

    def _ix(self, a, ix):
        b = self.rb(a + 1)
        # subconjunto soportado por las instrucciones IX/IY reales
        n = self.rb(a + 2)
        d = self.rb(a + 2)
        ds = d - 256 if d > 127 else d
        nn = self._imm16(a + 2)
        x, y, z = b >> 6, (b >> 3) & 7, b & 7
        p, q = y >> 1, y & 1
        def IXR(r): return r.replace('HL', ix).replace('H', ix+'h').replace('L', ix+'l') if r in ('H','L','HL') else r
        if b == 0xCB:
            b2 = self.rb(a + 3)
            x2, y2, z2 = b2 >> 6, (b2 >> 3) & 7, b2 & 7
            if x2 == 0: return (4, f'{ROT[y2]} ({ix}{ds:+d})', [], False)
            op = ['BIT', 'RES', 'SET'][x2 - 1]
            return (4, f'{op} {y2},({ix}{ds:+d})', [], False)
        if b == 0x21: return (4, f'LD {ix},{nn:#06x}', [], False)
        if b == 0x22: return (4, f'LD ({nn:#06x}),{ix}', [], False)
        if b == 0x2A: return (4, f'LD {ix},({nn:#06x})', [], False)
        if b == 0x36: return (4, f'LD ({ix}{ds:+d}),{self.rb(a+3):#04x}', [], False)
        if b == 0x23: return (2, f'INC {ix}', [], False)
        if b == 0x2B: return (2, f'DEC {ix}', [], False)
        if b == 0xE5: return (2, f'PUSH {ix}', [], False)
        if b == 0xE1: return (2, f'POP {ix}', [], False)
        if b == 0xE9: return (2, f'JP ({ix})', [], True)
        if b == 0x09: return (2, f'ADD {ix},BC', [], False)
        if b == 0x19: return (2, f'ADD {ix},DE', [], False)
        if b == 0x29: return (2, f'ADD {ix},{ix}', [], False)
        if b == 0x39: return (2, f'ADD {ix},SP', [], False)
        if x == 1 and (z == 6 or y == 6):     # LD r,(ix+d) / LD (ix+d),r
            if z == 6 and y != 6: return (3, f'LD {R[y]},({ix}{ds:+d})', [], False)
            if y == 6 and z != 6: return (3, f'LD ({ix}{ds:+d}),{R[z]}', [], False)
        if x == 2 and z == 6:                 # ALU A,(ix+d)
            return (3, f'{ALU[y]}({ix}{ds:+d})', [], False)
        if b in (0x34, 0x35):                 # INC/DEC (ix+d)
            return (3, f'{"INC" if b==0x34 else "DEC"} ({ix}{ds:+d})', [], False)
        # fallback: trata el prefijo como NOP y sigue (raro en código real)
        return (1, f'DB 0x{self.rb(a):02X}', [], False)

    # -- descenso recursivo desde los entry points
    def walk(self, entries):
        stack = list(entries)
        while stack:
            a = stack.pop()
            while self.inside(a):
                idx = a - self.org
                if self.code[idx]:
                    break                      # ya visitado
                length, text, targets, term = self.decode(a)
                self.code[idx] = 1
                self.insns[a] = (length, text, targets)
                for t in targets:
                    if self.inside(t):
                        self.label.setdefault(t, None)
                        stack.append(t)
                if term:
                    break
                a += length

    def assign_labels(self):
        for a in sorted(self.label):
            if self.code[a - self.org]:
                self.label[a] = f'L{a:04X}'

    def emit(self, path):
        out = []
        a = self.org
        while a < self.end:
            idx = a - self.org
            if self.label.get(a):
                out.append(f'\n; --- {self.label[a]} ---')
            if self.code[idx]:
                length, text, _ = self.insns[a]
                # resolver targets {XXXX} a etiquetas si existen
                for tgt in [t for (_, _, ts) in [self.insns[a]] for t in ts]:
                    key = f'{{{tgt:04X}}}'
                    name = self.label.get(tgt) or f'0x{tgt:04X}'
                    text = text.replace(key, name)
                # anotar llamadas BIOS
                raw = ' '.join(f'{self.rb(a+i):02X}' for i in range(length))
                bio = ''
                for tgt in [t for (_, _, ts) in [self.insns[a]] for t in ts]:
                    if tgt in BIOS: bio = f'   ; BIOS:{BIOS[tgt]}'
                out.append(f'  {a:04X}  {raw:<11} {text}{bio}')
                a += length
            else:
                # bloque de datos: agrupar hasta el próximo código/etiqueta
                run = []
                start = a
                while a < self.end and not self.code[a - self.org]:
                    run.append(self.rb(a)); a += 1
                    if self.label.get(a): break
                for i in range(0, len(run), 8):
                    chunk = run[i:i+8]
                    db = ', '.join(f'0x{x:02X}' for x in chunk)
                    asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in chunk)
                    out.append(f'  {start+i:04X}  DB {db:<40} ; {asc}')
        with open(path, 'w') as f:
            f.write('\n'.join(out) + '\n')
        ncode = sum(self.code)
        return ncode, len(self.rom) - ncode


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    rom = open(sys.argv[1], 'rb').read()
    org = 0x4000
    if '--org' in sys.argv:
        org = int(sys.argv[sys.argv.index('--org') + 1], 0)
    d = Disasm(rom, org)
    # entry points del cartucho MSX: header en org (AB, INIT, STATEMENT,
    # DEVICE, TEXT). INIT = word en org+2.
    init = d.rw(org + 2)
    statement = d.rw(org + 4)
    entries = [e for e in (init, statement) if d.inside(e)]
    # entradas extra (código alcanzado por saltos indirectos / tablas) que el
    # descenso estático no encuentra solo: --seed 0xADDR [0xADDR ...]
    if '--seed' in sys.argv:
        i = sys.argv.index('--seed') + 1
        while i < len(sys.argv) and sys.argv[i].startswith('0x'):
            entries.append(int(sys.argv[i], 0)); i += 1
    d.label.update({e: None for e in entries})
    d.walk(entries)
    d.assign_labels()
    ncode, ndata = d.emit(sys.argv[2])
    print(f'org={org:#06x} init={init:#06x}  código={ncode}B  datos={ndata}B  -> {sys.argv[2]}')


if __name__ == '__main__':
    main()
