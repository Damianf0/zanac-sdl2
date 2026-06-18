#!/usr/bin/env python3
"""Transcripción fiel del rebuild del scroll (0x9888-0x9A67) sobre imagen
RAM+ROM, validada contra el estado RAM completo capturado de openMSX."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
before = bytearray(open(os.path.join(ROOT, 'tick_before.bin'), 'rb').read())
after = open(os.path.join(ROOT, 'tick_after.bin'), 'rb').read()
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
def rd16(a): return rd(a) | (rd(a + 1) << 8)
def wr16(a, v): wr(a, v & 0xFF); wr(a + 1, (v >> 8) & 0xFF)

IX = 0xE700

# --- prólogo 0x9888-0x98D2 ---
A = rd(0xE702) & 0x03
A = ((3 * A) << 3) & 0xFF               # ADD A,A;ADD A,C;ADD A,A;ADD A,A;ADD A,A
wr16(0xE2AE, (0xA444 + A) & 0xFFFF)      # B=0 -> BC=A
A = rd(0xE702) & 0x07
de = ((3 * A) << 3) & 0xFFFF             # L=A;A+=A;A+=L;L=A;H=0;HL+=HL;HL+=HL;HL+=HL
wr16(0xE2B0, (0xA4A4 + de) & 0xFFFF)
wr16(0xE2B2, (0xA564 + de) & 0xFFFF)
wr(IX + 23, rd(IX + 28))
wr(IX + 25, 0); wr(IX + 24, 0)
wr16(0xE71A, 0xEA40)

# --- driver loop 0x98D4 (4 entradas E2C0, stride 8) ---
def expand_run(A, HL, iy):                # núcleo expansor 0x9A2C
    A = (A + rd(HL)) & 0xFF; HL = (HL + 1) & 0xFFFF
    de = (0xEA40 + A) & 0xFFFF
    cnt = rd(HL); HL = (HL + 1) & 0xFFFF
    if cnt != 0 and cnt < 0xFE:
        for _ in range(cnt):
            wr(de, rd(HL)); HL = (HL + 1) & 0xFFFF; de = (de + 1) & 0xFFFF
    wr16(iy + 2, HL)
    v = (rd(iy + 1) - 1) & 0xFF; wr(iy + 1, v)
    if v == 0: wr(iy, 0x80)

def driver_entry(iy):
    A = rd(iy + 0)
    if A == 0x80: return
    # 0x98DD DEC (IY+6)
    v6 = (rd(iy + 6) - 1) & 0xFF; wr(iy + 6, v6)
    HL = 0
    if v6 != 0:
        pass  # -> 0x992E (emit)
    else:
        a7 = rd(iy + 7)
        if a7 == 0:
            HL = rd16(iy + 2)             # 0x9926
            HL = reload_at_9901(iy, HL)
        else:
            v7 = (a7 - 1) & 0xFF; wr(iy + 7, v7)
            if v7 != 0:
                HL = rd16(iy + 2)         # 0x9926
                HL = reload_at_9901(iy, HL)
            else:
                HL = (rd16(iy + 2) + 3) & 0xFFFF   # 0x98ED INC x3
                HL = reload_loop_98F6(iy, HL)
    emit_992E(iy)

def reload_loop_98F6(iy, HL):
    # 0x98F6: bucle de lectura del programa hasta byte no-cero / no-0xFF
    while True:
        A = rd(HL); wr(iy + 7, A); HL = (HL + 1) & 0xFFFF
        wr16(iy + 2, HL)
        # 0x9901
        A6 = rd(HL); wr(iy + 6, A6); HL = (HL + 1) & 0xFFFF
        word = rd16(HL); HL = (HL + 2) & 0xFFFF
        de = HL                           # EX DE,HL -> DE=prog
        HL = word
        if A6 == 0:
            continue                      # JR Z 0x98F6
        if A6 == 0xFF:                    # 0x990F comando
            A = (rd(iy + 7) + rd(iy + 0)) & 0xFF; wr(iy + 0, A)
            HL = (de - 1) & 0xFFFF        # EX DE,HL; DEC HL
            continue                      # JR 0x98F6
        wr16(iy + 4, HL)                  # 0x991E ptr2 = word
        return HL

def reload_at_9901(iy, HL):
    # entra en 0x9901 con HL = (IY+2)
    A6 = rd(HL); wr(iy + 6, A6); HL = (HL + 1) & 0xFFFF
    word = rd16(HL); HL = (HL + 2) & 0xFFFF
    de = HL; HL = word
    if A6 == 0:
        return reload_loop_98F6(iy, HL_after_98F6_from_zero(iy, HL))
    if A6 == 0xFF:
        A = (rd(iy + 7) + rd(iy + 0)) & 0xFF; wr(iy + 0, A)
        HL = (de - 1) & 0xFFFF
        return reload_loop_98F6(iy, HL)
    wr16(iy + 4, HL)
    return HL

def HL_after_98F6_from_zero(iy, HL):
    return HL

def emit_992E(iy):
    pos = rd(iy + 0)
    if pos >= 0x28:
        wr(iy + 0, 0x80); return
    B = pos
    C = rd(IX + 25)
    if C >= B:                            # CP B; JR NC 0x99B5
        de = adjust_99B5(iy, B)
    else:
        # 0x993E selección de segmento + copia (B-C) bytes
        idx = (rd(iy + 1) >> 3) & 0x0E
        segptr = rd16(0xE2AC + idx)
        HL = (segptr + C) & 0xFFFF
        cnt = (B - C) & 0xFF
        de = rd16(0xE71A)
        for _ in range(cnt):
            wr(de, rd(HL)); HL = (HL + 1) & 0xFFFF; de = (de + 1) & 0xFFFF
    x1_9962(iy, B, de)                    # DE heredado (no se relee de E71A)

def adjust_99B5(iy, B):
    HL = rd16(0xE71A)                     # 0x99B5
    A = (rd(IX + 25) - B) & 0xFF
    if A != 0:
        A = (((~A) & 0xFF) + 1) & 0xFF    # CPL; INC A
        HL = (HL + (A | 0xFF00)) & 0xFFFF # ADD HL,DE con D=0xFF
    return HL                             # EX DE,HL -> DE=HL

def x1_9962(iy, B, de):
    # 0x9962: C=pos; (IX+24)=pos; HL=ptr2(IY+4); escribe a DE heredado
    C = B
    wr(IX + 24, B)
    HL = rd16(iy + 4)
    cnt = rd(HL); HL = (HL + 1) & 0xFFFF
    mode = rd(HL); HL = (HL + 1) & 0xFFFF
    if mode != 0:
        if rd(iy + 1) & 0x80:             # BIT 7: suma tile-base
            base = 0x2E if (rd(iy + 1) & 0x08) else 0x17
            for _ in range(mode):         # B=count (=A=mode), LD B,A
                wr(de, (rd(HL) + base) & 0xFF); HL = (HL + 1) & 0xFFFF; de = (de + 1) & 0xFFFF
        else:
            for _ in range(mode):
                wr(de, rd(HL)); HL = (HL + 1) & 0xFFFF; de = (de + 1) & 0xFFFF
    wr16(0xE71A, de)                      # 0x9995
    A = (mode + C) & 0xFF; wr(IX + 25, A) # 0x9999 POP AF; ADD A,C; (IX+25)=A
    wr16(iy + 4, HL)                      # 0x999E
    A = (rd(iy + 0) + cnt) & 0xFF; wr(iy + 0, A)  # 0x99A4 (IY+0)+=count
    wr(IX + 23, rd(iy + 1))               # 0x99AC

for k in range(4):
    driver_entry(0xE2C0 + k * 8)

# --- fetch 0x99D2-0x99F5 ---
col = rd(IX + 25)
if col < 0x20:
    idx = rd(IX + 23) & 7
    ptr = rd16(0xE2AC + idx * 2)
    src = (ptr + col) & 0xFFFF
    de = rd16(0xE71A)
    for i in range(0x20 - col):
        wr(de, rd((src + i) & 0xFFFF)); de = (de + 1) & 0xFFFF

# --- expansor 0x99F7-0x9A67 ---
iy = 0xE2E0
for b in range(8):
    A = rd(iy + 0)
    if A == 0x80: pass
    elif (A & 0x40) == 0:
        expand_run(A, rd16(iy + 2), iy)
    else:
        v = (rd(iy + 1) - 1) & 0xFF; wr(iy + 1, v)
        if v == 0:
            de = rd16(iy + 2); a2 = rd(de); de = (de + 1) & 0xFFFF
            wr(iy + 1, a2)
            wr(iy + 0, rd(iy + 0) & ~0x40)
            expand_run(rd(iy + 0), de, iy)
    iy += 4
hl = 0xEA48; de = rd16(0xE715)
for _ in range(0x18):
    wr(de, rd(hl)); hl = (hl + 1) & 0xFFFF; de = (de + 1) & 0xFFFF

bad = [i for i in range(0xC00) if ram[i] != after[i]]
print("bytes RAM 0xE000-0xEBFF que difieren:", len(bad))
for i in bad[:30]:
    print("  %04X: mine=%02X after=%02X (before=%02X)" % (0xE000 + i, ram[i], after[i], before[i]))
