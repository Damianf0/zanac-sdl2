#!/usr/bin/env python3
"""Transcripción fiel del command handler + spawn (0x95A8/0x95C0/0x95ED/0x9B22)
sobre imagen RAM+ROM, validada contra el estado RAM completo de openMSX."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
before = bytearray(open(os.path.join(ROOT, 'cmd_before.bin'), 'rb').read())
after = open(os.path.join(ROOT, 'cmd_after.bin'), 'rb').read()
rom = open(os.path.join(ROOT, 'zanac.rom'), 'rb').read()
ram = bytearray(before)

def rd(a):
    a &= 0xFFFF
    if 0xE000 <= a < 0xEC00: return ram[a - 0xE000]
    if 0x4000 <= a < 0xC000: return rom[a - 0x4000]
    return 0xFF
def wr(a, v):
    a &= 0xFFFF
    if 0xE000 <= a < 0xEC00: ram[a - 0xE000] = v & 0xFF

IX = 0xE700

# regs de entrada (cmd_regs.txt): HL=A761, BC=0000, DE=0032, IY=E380
HL = 0xA761; C = 0x00

# --- 0x9B22: busca slot vacío en la tabla 0xE620 (21 entradas, stride 0x20).
# Devuelve (carry, HL_slot). carry=1 -> sin slot. ---
def slot_finder():
    HLp = 0xE620
    B = 0x15
    while True:                                  # 0x9B2C
        if (rd(HLp) & 0xFF) == 0: return (False, HLp)
        HLp = (HLp - 0x20) & 0xFFFF
        B -= 1
        if B == 0: break
    HLp = (HLp + 0x20) & 0xFFFF                   # 0x9B33: HL+=0x20 (deshace último -0x20)
    B = 0x15
    while True:                                   # 0x9B38
        HLp = (HLp + 0x20) & 0xFFFF
        a = rd(HLp) & 0x7F
        if a == 0x14 or a == 0x25 or a == 0x26: return (False, HLp)
        B -= 1
        if B == 0: break
    B = 0x15
    while True:                                   # 0x9B4F
        a = rd(HLp) & 0x7F
        if a == 0x27 or a >= 0x46:                # CP 27 Z->9B5D ; CP 46 NC->9B5D
            HLp = (HLp - 0x20) & 0xFFFF            # 0x9B5D
            B -= 1
            if B == 0: break
            continue
        # AND A (clear carry) ; JR 0x9B61
        return (False, HLp)
    return (True, HLp)                            # 0x9B60 SCF

# --- 0x95ED: setup de objeto/spawn. DE = source (tras el byte 0). ---
def spawn(DE, iy):
    A = rd(DE); DE = (DE + 1) & 0xFFFF
    ret_A = A                                     # PUSH AF (se restaura al final como retorno)
    sC = rd(DE); DE = (DE + 1) & 0xFFFF           # 0x95F2 A=(DE)
    Cs = sC
    B = sC & 0x1F                                 # 0x95F7 B=A&0x1F
    if sC & 0x80:                                 # BIT 7,C
        mwr_hl = 0xE780
        wr16(0xE71E, mwr_hl)
        wr(0xE151, 0)
    # 0x9606 LOOP (B veces)
    while True:
        carry, HLs = slot_finder()                # 0x9607
        if carry:                                 # 0x960A JR NC -> si carry, NO salta
            DE = (DE + 3) & 0xFFFF                 # 0x960C INC DE x3
            if (Cs & 0x40) == 0: pass             # BIT 6,C ; JP Z 0x9662
            else:
                wr(IX + 29, (rd(IX + 29) + 1) & 0xFF)
                if (Cs & 0x20):                   # BIT 5,C
                    wr(IX + 29, (rd(IX + 29) + 1) & 0xFF)
        else:                                     # 0x9622 slot encontrado en HLs
            if Cs & 0x80:                         # BIT 7,C ; JR Z 0x963A
                # EX DE,HL ; guarda DE en (0xE71E) ; ...
                hp = rd16(0xE71E)
                wr(hp, DE & 0xFF); wr((hp + 1) & 0xFFFF, (DE >> 8) & 0xFF)
                hp = (hp + 4) & 0xFFFF
                wr16(0xE71E, hp)
                wr(0xE151, (rd(0xE151) + 1) & 0xFF)
            # 0x963A: copia 2 bytes (DE)->(HLs), luego tercer byte -> calculo tile
            wr(HLs, rd(DE)); HLs = (HLs + 1) & 0xFFFF; DE = (DE + 1) & 0xFFFF
            wr(HLs, rd(DE)); HLs = (HLs + 1) & 0xFFFF; DE = (DE + 1) & 0xFFFF
            Bb = rd(DE); DE = (DE + 1) & 0xFFFF
            A = (rd(iy + 0) << 3) & 0xFF          # ADD A,A x3
            A = (A + Bb) & 0xFF
            A = (A - 0x20) & 0xFF
            wr(HLs, A);
            if Cs & 0x40:                         # BIT 6,C
                HLs = (HLs + 1) & 0xFFFF
                wr(HLs, rd(IX + 29))
                wr(IX + 29, (rd(IX + 29) + 1) & 0xFF)
                if Cs & 0x20:                     # BIT 5,C
                    wr(IX + 29, (rd(IX + 29) + 1) & 0xFF)
        B -= 1                                     # 0x9663 DJNZ
        if B == 0: break
    if Cs & 0x80:                                  # 0x9665 BIT 7,C
        wr(0xE152, rd(0xE151))
        wr(0xE150, 1)
    return ret_A, DE                               # POP AF -> A ; DE avanzado

def rd16(a): return rd(a) | (rd((a + 1) & 0xFFFF) << 8)
def wr16(a, v): wr(a, v & 0xFF); wr((a + 1) & 0xFFFF, (v >> 8) & 0xFF)

# --- 0x95C0: setup de una columna (IY), C = tile base ---
def setup_col(HL, iy, E):
    A = (rd(HL) + C) & 0xFF; wr(iy + 0, A)        # 0x95C0
    if E & 0x08:                                   # BIT 3,E
        wr(iy + 0, rd(iy + 0) | 0x40)             # SET 6
        HL = (HL + 1) & 0xFFFF
        wr(iy + 1, rd(HL))
    HL = (HL + 1) & 0xFFFF                          # 0x95D2 INC HL
    DE = rd16(HL); HL = (HL + 2) & 0xFFFF
    if (rd(iy + 0) & 0x40) == 0:                   # BIT 6,(IY+0)
        A = rd(DE); DE = (DE + 1) & 0xFFFF
        if A == 0: A, DE = spawn(DE, iy)          # CALL Z 0x95ED (A=(DE) era 0)
        wr(iy + 1, A)
    wr(iy + 2, DE & 0xFF); wr(iy + 3, (DE >> 8) & 0xFF)
    return HL

# --- 0x95A8: loop de columnas ---
B = rd(HL); HL = (HL + 1) & 0xFFFF                  # B = count
while True:
    A = rd(HL) & 0xF7                              # RES 3
    A = (A << 2) & 0xFF                            # ADD A,A x2
    iy = (0xE2E0 + A) & 0xFFFF
    E = rd(HL); HL = (HL + 1) & 0xFFFF             # E = selector (con bit3)
    HL = setup_col(HL, iy, E)
    B -= 1
    if B == 0: break

bad = [i for i in range(0xC00) if ram[i] != after[i]]
print("bytes RAM 0xE000-0xEBFF que difieren:", len(bad))
for i in bad[:30]:
    print("  %04X: mine=%02X after=%02X (before=%02X)" % (0xE000 + i, ram[i], after[i], before[i]))
