#!/usr/bin/env python3
"""VM de script de nivel + fill inicial (0x9405 init + 0x946E ×24). Valida el
buffer 0xE800 generado contra lf_after.bin (captura openMSX). Reusa la logica
ya validada de rebuild (0x9888) y command (0x95A8)."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
before = bytearray(open(os.path.join(ROOT, 'tests/fixtures/lf_before.bin'), 'rb').read())
after = open(os.path.join(ROOT, 'tests/fixtures/lf_after.bin'), 'rb').read()
rom = open(os.path.join(ROOT, 'zanac.rom'), 'rb').read()
ram = bytearray(before)
IX = 0xE700
SCRIPT = 0xA751   # HL al entrar a 0x9405 (script nivel 1)

def rd(a):
    a &= 0xFFFF
    if 0xE000 <= a < 0xEC00: return ram[a-0xE000]
    if 0x4000 <= a < 0xC000: return rom[a-0x4000]
    return 0xFF
def wr(a, v):
    a &= 0xFFFF
    if 0xE000 <= a < 0xEC00: ram[a-0xE000] = v & 0xFF
def r16(a): return rd(a) | (rd(a+1) << 8)
def w16(a, v): wr(a, v & 0xFF); wr(a+1, (v >> 8) & 0xFF)

# ===================== rebuild (0x9888, validado) =====================
def expand_run(A, HL, iy):
    A = (A + rd(HL)) & 0xFF; HL = (HL+1) & 0xFFFF
    de = (0xEA40 + A) & 0xFFFF
    cnt = rd(HL); HL = (HL+1) & 0xFFFF
    if cnt and cnt < 0xFE:
        for _ in range(cnt):
            wr(de, rd(HL)); HL = (HL+1)&0xFFFF; de = (de+1)&0xFFFF
    w16(iy+2, HL); v=(rd(iy+1)-1)&0xFF; wr(iy+1,v)
    if v == 0: wr(iy, 0x80)

def rb_reload_98F6(iy, HL):
    while True:
        a7=rd(HL); wr(iy+7,a7); HL=(HL+1)&0xFFFF; w16(iy+2,HL)
        a6=rd(HL); wr(iy+6,a6); HL=(HL+1)&0xFFFF
        word=r16(HL); HL=(HL+2)&0xFFFF; de=HL; HL=word
        if a6==0: continue
        if a6==0xFF:
            wr(iy+0,(rd(iy+7)+rd(iy+0))&0xFF); HL=(de-1)&0xFFFF; continue
        w16(iy+4,HL); return

def rb_reload_9901(iy, HL):
    a6=rd(HL); wr(iy+6,a6); HL=(HL+1)&0xFFFF
    word=r16(HL); HL=(HL+2)&0xFFFF; de=HL; HL=word
    if a6==0: rb_reload_98F6(iy,HL); return
    if a6==0xFF:
        wr(iy+0,(rd(iy+7)+rd(iy+0))&0xFF); rb_reload_98F6(iy,(de-1)&0xFFFF); return
    w16(iy+4,HL)

def rb_x1(iy, pos, de):
    C=pos; wr(IX+24,pos); HL=r16(iy+4)
    cnt=rd(HL); HL=(HL+1)&0xFFFF; mode=rd(HL); HL=(HL+1)&0xFFFF
    if mode:
        if rd(iy+1)&0x80:
            base=0x2E if (rd(iy+1)&0x08) else 0x17
            for _ in range(mode): wr(de,(rd(HL)+base)&0xFF); HL=(HL+1)&0xFFFF; de=(de+1)&0xFFFF
        else:
            for _ in range(mode): wr(de,rd(HL)); HL=(HL+1)&0xFFFF; de=(de+1)&0xFFFF
    w16(0xE71A,de); wr(IX+25,(mode+C)&0xFF); w16(iy+4,HL)
    wr(iy+0,(rd(iy+0)+cnt)&0xFF); wr(IX+23,rd(iy+1))

def rb_emit(iy):
    pos=rd(iy+0)
    if pos>=0x28: wr(iy+0,0x80); return
    C=rd(IX+25)
    if C>=pos:
        HL=r16(0xE71A); a=(C-pos)&0xFF
        if a: a=(((~a)&0xFF)+1)&0xFF; HL=(HL+(a|0xFF00))&0xFFFF
        de=HL
    else:
        idx=(rd(iy+1)>>3)&0x0E; HL=(r16(0xE2AC+idx)+C)&0xFFFF
        cnt=(pos-C)&0xFF; de=r16(0xE71A)
        for _ in range(cnt): wr(de,rd(HL)); HL=(HL+1)&0xFFFF; de=(de+1)&0xFFFF
    rb_x1(iy,pos,de)

def rb_driver_entry(iy):
    if rd(iy+0)==0x80: return
    v6=(rd(iy+6)-1)&0xFF; wr(iy+6,v6)
    if v6!=0: rb_emit(iy); return
    a7=rd(iy+7)
    if a7==0: rb_reload_9901(iy,r16(iy+2))
    else:
        v7=(a7-1)&0xFF; wr(iy+7,v7)
        if v7!=0: rb_reload_9901(iy,r16(iy+2))
        else: rb_reload_98F6(iy,(r16(iy+2)+3)&0xFFFF)
    rb_emit(iy)

def rebuild():
    a=rd(0xE702)&0x03; a=((3*a)<<3)&0xFF; w16(0xE2AE,(0xA444+a)&0xFFFF)
    de=((3*(rd(0xE702)&0x07))<<3)&0xFFFF; w16(0xE2B0,(0xA4A4+de)&0xFFFF); w16(0xE2B2,(0xA564+de)&0xFFFF)
    wr(IX+23,rd(IX+28)); wr(IX+25,0); wr(IX+24,0); w16(0xE71A,0xEA40)
    for k in range(4): rb_driver_entry(0xE2C0+k*8)
    col=rd(IX+25)
    if col<0x20:
        ptr=r16(0xE2AC+(rd(IX+23)&7)*2); src=(ptr+col)&0xFFFF; d=r16(0xE71A)
        for i in range(0x20-col): wr(d,rd((src+i)&0xFFFF)); d=(d+1)&0xFFFF
    iy=0xE2E0
    for b in range(8):
        A=rd(iy+0)
        if A==0x80: pass
        elif (A&0x40)==0: expand_run(A,r16(iy+2),iy)
        else:
            v=(rd(iy+1)-1)&0xFF; wr(iy+1,v)
            if v==0:
                de=r16(iy+2); a2=rd(de); de=(de+1)&0xFFFF; wr(iy+1,a2)
                wr(iy+0,rd(iy+0)&~0x40); expand_run(rd(iy+0),de,iy)
        iy+=4
    hl=0xEA48; de=r16(0xE715)
    for _ in range(0x18): wr(de,rd(hl)); hl=(hl+1)&0xFFFF; de=(de+1)&0xFFFF

# ===================== command (0x95A8, validado) =====================
def slot_finder():
    HL=0xE620; B=0x15
    while True:
        if (rd(HL)&0xFF)==0: return (False,HL)
        HL=(HL-0x20)&0xFFFF; B-=1
        if B==0: break
    HL=(HL+0x20)&0xFFFF; B=0x15
    while True:
        HL=(HL+0x20)&0xFFFF; a=rd(HL)&0x7F
        if a in (0x14,0x25,0x26): return (False,HL)
        B-=1
        if B==0: break
    B=0x15
    while True:
        a=rd(HL)&0x7F
        if a==0x27 or a>=0x46:
            HL=(HL-0x20)&0xFFFF; B-=1
            if B==0: break
            continue
        return (False,HL)
    return (True,HL)

def spawn(de, iy):
    ret_A=rd(de); de=(de+1)&0xFFFF; Cs=rd(de); de=(de+1)&0xFFFF; B=Cs&0x1F
    if Cs&0x80: w16(0xE71E,0xE780); wr(0xE151,0)
    while True:
        carry,HLs=slot_finder()
        if carry:
            de=(de+3)&0xFFFF
            if Cs&0x40:
                wr(IX+29,(rd(IX+29)+1)&0xFF)
                if Cs&0x20: wr(IX+29,(rd(IX+29)+1)&0xFF)
        else:
            if Cs&0x80:
                hp=r16(0xE71E); wr(hp,de&0xFF); wr((hp+1)&0xFFFF,(de>>8)&0xFF)
                hp=(hp+4)&0xFFFF; w16(0xE71E,hp); wr(0xE151,(rd(0xE151)+1)&0xFF)
            wr(HLs,rd(de)); HLs=(HLs+1)&0xFFFF; de=(de+1)&0xFFFF
            wr(HLs,rd(de)); HLs=(HLs+1)&0xFFFF; de=(de+1)&0xFFFF
            Bb=rd(de); de=(de+1)&0xFFFF
            A=(((rd(iy+0)<<3)&0xFF)+Bb)&0xFF; A=(A-0x20)&0xFF; wr(HLs,A)
            if Cs&0x40:
                HLs=(HLs+1)&0xFFFF; wr(HLs,rd(IX+29)); wr(IX+29,(rd(IX+29)+1)&0xFF)
                if Cs&0x20: wr(IX+29,(rd(IX+29)+1)&0xFF)
        B-=1
        if B==0: break
    if Cs&0x80: wr(0xE152,rd(0xE151)); wr(0xE150,1)
    return ret_A, de

def setup_col(HL, iy, E, C):
    wr(iy+0,(rd(HL)+C)&0xFF)
    if E&0x08:
        wr(iy+0,rd(iy+0)|0x40); HL=(HL+1)&0xFFFF; wr(iy+1,rd(HL))
    HL=(HL+1)&0xFFFF; de=r16(HL); HL=(HL+2)&0xFFFF
    if (rd(iy+0)&0x40)==0:
        A=rd(de); de=(de+1)&0xFFFF
        if A==0: A,de=spawn(de,iy)
        wr(iy+1,A)
    wr(iy+2,de&0xFF); wr(iy+3,(de>>8)&0xFF)
    return HL

def command(HL, C):
    B=rd(HL); HL=(HL+1)&0xFFFF
    while True:
        A=((rd(HL)&0xF7)<<2)&0xFF; iy=(0xE2E0+A)&0xFFFF
        E=rd(HL); HL=(HL+1)&0xFFFF
        HL=setup_col(HL,iy,E,C)
        B-=1
        if B==0: break
    return HL

# ===================== handlers del VM =====================
# Devuelven el nuevo HL (script ptr) o None para terminar/redirigir.
def h_2(HL):  # 0x9505 arma entradas E2C0
    B=rd(HL); HL=(HL+1)&0xFFFF
    for _ in range(B):
        A=(rd(HL)<<3)&0xFF; HL=(HL+1)&0xFFFF; iy=(0xE2C0+A)&0xFFFF
        wr(iy+0,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+1,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+2,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+3,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+6,1); wr(iy+7,1)
    return HL
def h_4(HL):  # 0x956C como h_2 pero (IY+0)+=
    B=rd(HL); HL=(HL+1)&0xFFFF
    for _ in range(B):
        A=(rd(HL)<<3)&0xFF; HL=(HL+1)&0xFFFF; iy=(0xE2C0+A)&0xFFFF
        wr(iy+0,(rd(iy+0)+rd(HL))&0xFF); HL=(HL+1)&0xFFFF
        wr(iy+1,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+2,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+3,rd(HL)); HL=(HL+1)&0xFFFF
        wr(iy+6,1); wr(iy+7,1)
    return HL
def h_5(HL):  # 0x95A0 C=0; command
    return command(HL,0)
def h_6(HL):  # 0x9678 (E71C)=byte
    wr(0xE71C,rd(HL)); return (HL+1)&0xFFFF
def h_7(HL):  # 0x9680 marca E2C0=0x80
    B=rd(HL); HL=(HL+1)&0xFFFF
    for _ in range(B):
        A=(rd(HL)<<3)&0xFF; HL=(HL+1)&0xFFFF; wr((0xE2C0+A)&0xFFFF,0x80)
    return HL
def h_0(HL):  # 0x97A8 (E12D)=byte; si bit2 cae en h_1
    a=rd(HL); wr(0xE12D,a); HL=(HL+1)&0xFFFF
    if a&0x04: return h_1(HL)
    return HL
def h_1(HL):  # 0x97B3 spawn B objetos (0x45+3B)
    B=rd(HL); HL=(HL+1)&0xFFFF
    for _ in range(B):
        carry,HLs=slot_finder()
        if carry: HL=(HL+3)&0xFFFF
        else:
            wr(HLs,0x45); HLs=(HLs+1)&0xFFFF
            for _ in range(3): wr(HLs,rd(HL)); HLs=(HLs+1)&0xFFFF; HL=(HL+1)&0xFFFF
    return HL
def h_8(HL):  # 0x9699 sprite/score: consume 2 bytes (efectos no-buffer omitidos)
    de=r16(HL); HL=(HL+2)&0xFFFF; w16(0xE720,de); wr(IX+29,0)
    return HL
def h_10(HL): # 0x96E5 VRAM: (IX+35)=byte, consume 1 (efecto VRAM omitido)
    wr(IX+35,rd(HL)); return (HL+1)&0xFFFF
def h_11(HL): # 0x9742 LDIR 4B->E155; tabla; setup_col col0
    for i in range(4): wr(0xE155+i,rd(HL)); HL=(HL+1)&0xFFFF
    wr(0xE154,0); a=rd(0xE157)&0x1F; wr(0xE153,rd(0x976C+a))
    HL=setup_col(HL,0xE2E0,0,0)   # IY=E2E0, E=B=0, C=0
    return HL
def h_12(HL): # 0x977D dificultad/sonido: consume 1 byte (efectos omitidos)
    return (HL+1)&0xFFFF
def h_3(HL):  # 0x9537 mueve entradas E2 (LDI x7)
    B=rd(HL); HL=(HL+1)&0xFFFF
    for _ in range(B):
        dst=((rd(HL)<<3)+0xC0)&0xFF; de=0xE200|dst; HL=(HL+1)&0xFFFF
        src=((rd(HL)<<3)+0xC0)&0xFF; sh=0xE200|src; HL=(HL+1)&0xFFFF
        # EX DE,HL: copia 8 bytes de sh -> de, marca sh=0x80
        wr(de,rd(sh)); wr(sh,0x80); sh=(sh+1)&0xFFFF; de=(de+1)&0xFFFF
        for _ in range(7): wr(de,rd(sh)); sh=(sh+1)&0xFFFF; de=(de+1)&0xFFFF
    return HL

HANDLERS={0:h_0,1:h_1,2:h_2,3:h_3,4:h_4,5:h_5,6:h_6,7:h_7,8:h_8,10:h_10,11:h_11,12:h_12}

# ===================== VM core =====================
def vm_dispatch_once():
    # 0x94C3: INC E702 ; 0x94D1
    w16(0xE702,(r16(0xE702)+1)&0xFFFF)
    while True:                       # bucle 0x94D1<->0x97D5
        E702=r16(0xE702); E706=r16(0xE706)
        if E706!=E702:                # no vencido -> avanza scroll (0x97E3)
            C=(rd(IX+20)-1)&0xFF
            HL=r16(0xE715)
            if C&0x80:  C=0x17; HL=0xEA28
            else: HL=(HL+0xFFE8)&0xFFFF
            wr(IX+20,C); w16(0xE715,HL); rebuild()
            return
        # vencido -> ejecuta opcode (0x94DE)
        HL=r16(0xE704); op=rd(HL); wr(IX+15,op); HL=(HL+1)&0xFFFF
        idx=op&0x0F
        h=HANDLERS.get(idx)
        if h is None:
            print("OPCODE SIN HANDLER: idx",idx,"@HL",hex(HL)); return
        nh=h(HL)
        if nh is None: return
        # 0x97D5: fetch siguiente [trigger]
        HL=nh; E=rd(HL); HL=(HL+1)&0xFFFF; D=rd(HL); HL=(HL+1)&0xFFFF
        w16(0xE704,HL); w16(0xE706,(E|(D<<8)))
        # loop a 0x94D1

# init 0x9405-0x9432
wr(0xE710,0); wr(0xE711,0)
HL=SCRIPT
for k in range(16): wr(0xE2C0+k*4,0x80)
de=r16(HL); HL=(HL+2)&0xFFFF
w16(0xE706,de); w16(0xE702,(de-1)&0xFFFF); w16(0xE704,HL)
wr(IX+0,rd(IX+0)&~0x01)
# fill 0x946E: 24 pasos
for _ in range(0x18): vm_dispatch_once()

# comparar buffer 0xE800-0xEA3F (24x24) + bloques E2C0/E2E0
def region(s,e): return [i for i in range(s-0xE000,e-0xE000) if ram[i]!=after[i]]
b_buf=region(0xE800,0xEA40)
b_ctl=region(0xE2C0,0xE300)
print("buffer 0xE800-0xEA3F: %d/%d difieren"%(len(b_buf),0x240))
print("bloques E2C0-E2FF:    %d/64 difieren"%len(b_ctl))
for i in (b_buf+b_ctl)[:24]:
    print("  %04X: mine=%02X after=%02X"%(0xE000+i,ram[i],after[i]))
