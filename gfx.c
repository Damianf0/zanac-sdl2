/*
 * ZANAC — Descompresor de gráficos (sub_5CDC) portado del disasm.
 * ===============================================================
 * RLE anidado con escape, validado byte a byte contra openMSX (17264/17264
 * bytes de la carga del título). Formato (escape inicial 0xFF, flag=0):
 *   b != ESC          -> emite b, (flag? cuenta=*src++ : 1) veces
 *   ESC b2, b2 != ESC -> "devuelve" b2 y ALTERNA el flag (run con cuenta)
 *   ESC ESC cmd:
 *     cmd 0 -> FIN
 *     cmd 1 -> nuevo byte ESC = *src++
 *     cmd 2 -> repetir bloque: C=cuenta externa, luego [B=len, B valores];
 *              emite el bloque C veces (cada valor con su cuenta de flag)
 * Cuenta 0 = 256 (idiom DJNZ con B=0). emit() recibe cada byte de salida.
 */
#include <stdint.h>
#include "gfx.h"

extern const uint8_t *g_rom;
extern uint32_t       g_rom_size;

static uint8_t rb(uint16_t a)
{
    uint32_t o = (uint32_t)a - 0x4000u;
    return (g_rom && o < g_rom_size) ? g_rom[o] : 0xFFu;
}
static int cnt256(uint8_t x) { return x ? x : 256; }

/* sub_9A80: blit del scroll. Copia el buffer circular del mapa (24 filas ×
 * 24 cols, en 0xE800) al playfield de la name table (32 de ancho), empezando
 * por la fila `start` (= (0xE715 - 0xE800)/24, la posición de scroll) y
 * envolviendo cada 24 filas. Validado 24/24 vs openMSX. */
void z_blit_playfield(const uint8_t *buf, int start, uint8_t *nt /* 768B, 32-wide */)
{
    for (int row = 0; row < 24; row++) {
        const uint8_t *src = buf + ((start + row) % 24) * 24;
        uint8_t *dst = nt + row * 32;
        for (int col = 0; col < 24; col++) dst[col] = src[col];
    }
}

/* sub_9A80 entrada (0x99D2-0x99F5): FETCH de fila de mapa. Selecciona el
 * segmento ROM por (ix23 & 7) en la tabla seg_tbl[8] (= 0xE2AC), suma la
 * columna actual `col` (= IX+25) y copia (0x20 - col) bytes del mapa CRUDO
 * al staging. Si col >= 0x20 no copia nada (JR NC 0x99F7). Devuelve los
 * bytes copiados. Validado 32/32 vs openMSX (idx=3 → 0xA564, sección de
 * apertura). El staging tiene runs con prefijo de longitud (0x17 = run de
 * 23), que el expansor 0x99FD luego expande al buffer visible. */
uint16_t z_map_fetch(const uint16_t seg_tbl[8], uint8_t ix23, uint8_t ix25,
                     uint8_t *staging /* >= 32 bytes */)
{
    uint8_t col = ix25;
    if (col >= 0x20u) return 0;            /* JR NC 0x99F7: sin fetch */
    uint16_t ptr = seg_tbl[ix23 & 7u];
    uint16_t src = (uint16_t)(ptr + col);
    uint16_t len = (uint16_t)(0x20u - col);
    for (uint16_t i = 0; i < len; i++)
        staging[i] = rb((uint16_t)(src + i));
    return len;
}

/* sub_99FD-0x9A67: EXPANSOR de runs del scroll. Procesa las 8 "columnas" del
 * bloque de control 0xE2E0 (4 bytes c/u: tilebase+0, contador+1, ptr-programa
 * +2/+3). Cada columna lee su programa (en ROM, región del mapa) como runs
 * [destOffset, count, count tiles] y los copia al staging (0xEA40+); al final
 * copia 24 bytes de 0xEA48 al buffer visible en (0xE715). `ram` apunta a la
 * RAM mapeada en 0xE000 (>= 0xC00 bytes). Bit6 del flag = run multi-fila en
 * curso (sólo copia al expirar el contador); flag 0x80 = columna terminada.
 * Validado byte-exacto vs el estado RAM completo de openMSX (caso sin comando
 * 0xFE ni terminador 0x00). NOTA: no implementa el camino de comando (0x9A68
 * -> 0x95A8, spawn de objetos) ni el de recarga 0x95ED. */
static uint8_t mrd(const uint8_t *ram, uint16_t a)
{
    if (a >= 0xE000u && a < 0xEC00u) return ram[a - 0xE000u];
    return rb(a);
}
static void mwr(uint8_t *ram, uint16_t a, uint8_t v)
{
    if (a >= 0xE000u && a < 0xEC00u) ram[a - 0xE000u] = v;
}

/* núcleo común desde 0x9A2C: A += programa[0]; copia `count` tiles del
 * programa al staging 0xEA40+A; avanza ptr y contador de la columna. */
static void expand_run(uint8_t *ram, uint8_t A, uint16_t HL, uint16_t iy)
{
    A = (uint8_t)(A + mrd(ram, HL)); HL++;
    uint16_t de = (uint16_t)(0xEA40u + A);
    uint8_t cnt = mrd(ram, HL); HL++;
    if (cnt != 0 && cnt < 0xFEu) {           /* LDIR (count<0xFE, !=0) */
        for (uint8_t i = 0; i < cnt; i++) { mwr(ram, de++, mrd(ram, HL)); HL++; }
    }
    mwr(ram, iy + 2, HL & 0xFFu); mwr(ram, iy + 3, (HL >> 8) & 0xFFu);
    uint8_t v = (uint8_t)(mrd(ram, iy + 1) - 1); mwr(ram, iy + 1, v);
    if (v == 0) mwr(ram, iy + 0, 0x80u);     /* columna terminada */
}

void z_map_expand(uint8_t *ram /* base 0xE000, >=0xC00 */)
{
    uint16_t iy = 0xE2E0u;
    for (int b = 0; b < 8; b++, iy += 4) {
        uint8_t A = mrd(ram, iy + 0);
        if (A == 0x80u) continue;                       /* columna terminada */
        if ((A & 0x40u) == 0) {                         /* 0x9A26 normal */
            uint16_t HL = mrd(ram, iy + 2) | (mrd(ram, iy + 3) << 8);
            expand_run(ram, A, HL, iy);
        } else {                                        /* 0x9A08 especial */
            uint8_t v = (uint8_t)(mrd(ram, iy + 1) - 1); mwr(ram, iy + 1, v);
            if (v == 0) {                               /* contador expiró: recarga */
                uint16_t de = mrd(ram, iy + 2) | (mrd(ram, iy + 3) << 8);
                uint8_t a2 = mrd(ram, de++);
                /* a2==0 -> CALL 0x95ED (recarga de segmento, no portado) */
                mwr(ram, iy + 1, a2);
                uint16_t HL = de;
                mwr(ram, iy + 0, mrd(ram, iy + 0) & (uint8_t)~0x40u);
                expand_run(ram, mrd(ram, iy + 0), HL, iy);
            }
        }
    }
    /* 0x9A5B: copia 24 bytes 0xEA48 -> buffer visible en (0xE715) */
    uint16_t hl = 0xEA48u;
    uint16_t de = mrd(ram, 0xE715u) | (mrd(ram, 0xE716u) << 8);
    for (int i = 0; i < 0x18; i++) { mwr(ram, de++, mrd(ram, hl++)); }
}

static uint16_t mrd16(const uint8_t *ram, uint16_t a)
{
    return (uint16_t)(mrd(ram, a) | (mrd(ram, (uint16_t)(a + 1)) << 8));
}
static void mwr16(uint8_t *ram, uint16_t a, uint16_t v)
{
    mwr(ram, a, v & 0xFFu); mwr(ram, (uint16_t)(a + 1), (v >> 8) & 0xFFu);
}

#define IXB 0xE700u   /* base del bloque de control del scroll (IX) */

/* 0x98F6: bucle de lectura del programa de columna (E2C0) hasta byte de
 * timer no-cero/no-0xFF; 0xFF avanza la posición. Devuelve el ptr2 (IY+4/5). */
static uint16_t rb_reload_98F6(uint8_t *ram, uint16_t iy, uint16_t HL)
{
    for (;;) {
        uint8_t a7 = mrd(ram, HL); mwr(ram, iy + 7, a7); HL++;
        mwr16(ram, iy + 2, HL);
        uint8_t a6 = mrd(ram, HL); mwr(ram, iy + 6, a6); HL++;
        uint16_t word = mrd16(ram, HL); HL += 2;
        uint16_t de = HL; HL = word;
        if (a6 == 0) continue;                       /* JR Z 0x98F6 */
        if (a6 == 0xFFu) {                            /* 0x990F comando */
            mwr(ram, iy + 0, (uint8_t)(mrd(ram, iy + 7) + mrd(ram, iy + 0)));
            HL = (uint16_t)(de - 1); continue;
        }
        mwr16(ram, iy + 4, HL);                       /* 0x991E ptr2 */
        return HL;
    }
}
/* entra en 0x9901 (camino 0x9926: timer aún corriendo, recarga desde IY+2/3) */
static void rb_reload_9901(uint8_t *ram, uint16_t iy, uint16_t HL)
{
    uint8_t a6 = mrd(ram, HL); mwr(ram, iy + 6, a6); HL++;
    uint16_t word = mrd16(ram, HL); HL += 2;
    uint16_t de = HL; HL = word;
    if (a6 == 0) { rb_reload_98F6(ram, iy, HL); return; }
    if (a6 == 0xFFu) {
        mwr(ram, iy + 0, (uint8_t)(mrd(ram, iy + 7) + mrd(ram, iy + 0)));
        rb_reload_98F6(ram, iy, (uint16_t)(de - 1)); return;
    }
    mwr16(ram, iy + 4, HL);
}

/* 0x9962 (X1): copia los `mode` tiles del ptr2 al staging DE (sumando
 * tile-base 0x17/0x2E si bit7 de IY+1), avanza E71A, IX+25 e IY+0. */
static void rb_x1(uint8_t *ram, uint16_t iy, uint8_t pos, uint16_t de)
{
    uint8_t C = pos;
    mwr(ram, IXB + 24, pos);
    uint16_t HL = mrd16(ram, iy + 4);
    uint8_t cnt = mrd(ram, HL); HL++;
    uint8_t mode = mrd(ram, HL); HL++;
    if (mode != 0) {
        if (mrd(ram, iy + 1) & 0x80u) {              /* BIT 7: suma tile-base */
            uint8_t base = (mrd(ram, iy + 1) & 0x08u) ? 0x2Eu : 0x17u;
            for (uint8_t i = 0; i < mode; i++) { mwr(ram, de++, (uint8_t)(mrd(ram, HL) + base)); HL++; }
        } else {
            for (uint8_t i = 0; i < mode; i++) { mwr(ram, de++, mrd(ram, HL)); HL++; }
        }
    }
    mwr16(ram, 0xE71Au, de);                          /* 0x9995 */
    mwr(ram, IXB + 25, (uint8_t)(mode + C));          /* 0x9999 */
    mwr16(ram, iy + 4, HL);                           /* 0x999E */
    mwr(ram, iy + 0, (uint8_t)(mrd(ram, iy + 0) + cnt));  /* 0x99A4 += count */
    mwr(ram, IXB + 23, mrd(ram, iy + 1));             /* 0x99AC */
}

/* 0x992E: copia (pos - IX25) bytes del segmento ROM seleccionado por
 * (IY+1)>>3&0x0E al staging, luego X1; o ajusta DE (0x99B5) si IX25>=pos. */
static void rb_emit(uint8_t *ram, uint16_t iy)
{
    uint8_t pos = mrd(ram, iy + 0);
    if (pos >= 0x28u) { mwr(ram, iy + 0, 0x80u); return; }   /* fin de columna */
    uint8_t C = mrd(ram, IXB + 25);
    uint16_t de;
    if (C >= pos) {                                   /* 0x99B5 */
        uint16_t HL = mrd16(ram, 0xE71Au);
        uint8_t a = (uint8_t)(C - pos);
        if (a != 0) {
            a = (uint8_t)(((uint8_t)~a) + 1);         /* CPL; INC A */
            HL = (uint16_t)(HL + (a | 0xFF00u));      /* ADD HL,DE (D=0xFF) */
        }
        de = HL;
    } else {
        uint8_t idx = (uint8_t)((mrd(ram, iy + 1) >> 3) & 0x0Eu);
        uint16_t HL = (uint16_t)(mrd16(ram, 0xE2ACu + idx) + C);
        uint8_t cnt = (uint8_t)(pos - C);
        de = mrd16(ram, 0xE71Au);
        for (uint8_t i = 0; i < cnt; i++) { mwr(ram, de++, mrd(ram, HL)); HL++; }
    }
    rb_x1(ram, iy, pos, de);
}

/* 0x98D4: procesa una entrada del bloque E2C0 (8B: pos+0/+1, ptr+2/+3,
 * ptr2+4/+5, timer+6, timer2+7). */
static void rb_driver_entry(uint8_t *ram, uint16_t iy)
{
    if (mrd(ram, iy + 0) == 0x80u) return;
    uint8_t v6 = (uint8_t)(mrd(ram, iy + 6) - 1); mwr(ram, iy + 6, v6);  /* DEC (IY+6) */
    if (v6 != 0) {                                    /* timer corriendo -> emit */
        rb_emit(ram, iy); return;
    }
    uint8_t a7 = mrd(ram, iy + 7);
    if (a7 == 0) {
        rb_reload_9901(ram, iy, mrd16(ram, iy + 2));  /* 0x9926 */
    } else {
        uint8_t v7 = (uint8_t)(a7 - 1); mwr(ram, iy + 7, v7);
        if (v7 != 0) rb_reload_9901(ram, iy, mrd16(ram, iy + 2));
        else rb_reload_98F6(ram, iy, (uint16_t)(mrd16(ram, iy + 2) + 3));  /* 0x98ED */
    }
    rb_emit(ram, iy);
}

/* sub 0x9B22: busca un slot libre en la tabla de objetos 0xE620 (21 entradas,
 * stride 0x20). Devuelve 1 si NO hay slot (carry); *slot = puntero hallado. */
static int rb_slot_finder(const uint8_t *ram, uint16_t *slot)
{
    uint16_t HL = 0xE620u; int B = 0x15;
    for (;;) {                                    /* 0x9B2C */
        if ((mrd(ram, HL) & 0xFFu) == 0) { *slot = HL; return 0; }
        HL = (uint16_t)(HL - 0x20u); if (--B == 0) break;
    }
    HL = (uint16_t)(HL + 0x20u); B = 0x15;        /* 0x9B33 */
    for (;;) {                                    /* 0x9B38 */
        HL = (uint16_t)(HL + 0x20u);
        uint8_t a = mrd(ram, HL) & 0x7Fu;
        if (a == 0x14u || a == 0x25u || a == 0x26u) { *slot = HL; return 0; }
        if (--B == 0) break;
    }
    B = 0x15;
    for (;;) {                                    /* 0x9B4F */
        uint8_t a = mrd(ram, HL) & 0x7Fu;
        if (a == 0x27u || a >= 0x46u) { HL = (uint16_t)(HL - 0x20u); if (--B == 0) break; continue; }
        *slot = HL; return 0;                      /* AND A (sin carry) */
    }
    *slot = HL; return 1;                          /* 0x9B60 SCF */
}

/* sub 0x95ED: setup de objeto/spawn. `de` = source (tras el byte 0). Devuelve
 * A (contador) y deja *de_out avanzado. */
static uint8_t rb_spawn(uint8_t *ram, uint16_t de, uint16_t iy, uint16_t *de_out)
{
    uint8_t ret_A = mrd(ram, de); de++;
    uint8_t Cs = mrd(ram, de); de++;
    uint8_t B = Cs & 0x1Fu;
    if (Cs & 0x80u) { mwr16(ram, 0xE71Eu, 0xE780u); mwr(ram, 0xE151u, 0); }
    for (;;) {
        uint16_t slot;
        int carry = rb_slot_finder(ram, &slot);
        if (carry) {                               /* 0x960C sin slot */
            de = (uint16_t)(de + 3);
            if (Cs & 0x40u) {
                mwr(ram, IXB + 29, (uint8_t)(mrd(ram, IXB + 29) + 1));
                if (Cs & 0x20u) mwr(ram, IXB + 29, (uint8_t)(mrd(ram, IXB + 29) + 1));
            }
        } else {                                   /* 0x9622 slot hallado */
            if (Cs & 0x80u) {
                uint16_t hp = mrd16(ram, 0xE71Eu);
                mwr(ram, hp, de & 0xFFu); mwr(ram, (uint16_t)(hp + 1), (de >> 8) & 0xFFu);
                hp = (uint16_t)(hp + 4); mwr16(ram, 0xE71Eu, hp);
                mwr(ram, 0xE151u, (uint8_t)(mrd(ram, 0xE151u) + 1));
            }
            mwr(ram, slot, mrd(ram, de)); slot++; de++;     /* 0x963A */
            mwr(ram, slot, mrd(ram, de)); slot++; de++;
            uint8_t Bb = mrd(ram, de); de++;
            uint8_t A = (uint8_t)((mrd(ram, iy + 0) << 3) + Bb);
            A = (uint8_t)(A - 0x20u);
            mwr(ram, slot, A);
            if (Cs & 0x40u) {
                slot++; mwr(ram, slot, mrd(ram, IXB + 29));
                mwr(ram, IXB + 29, (uint8_t)(mrd(ram, IXB + 29) + 1));
                if (Cs & 0x20u) mwr(ram, IXB + 29, (uint8_t)(mrd(ram, IXB + 29) + 1));
            }
        }
        if (--B == 0) break;                       /* 0x9663 DJNZ */
    }
    if (Cs & 0x80u) { mwr(ram, 0xE152u, mrd(ram, 0xE151u)); mwr(ram, 0xE150u, 1); }
    *de_out = de;
    return ret_A;
}

/* sub 0x95C0: setup de una columna (entrada IY del bloque E2E0). `c` = tile
 * base. Devuelve el puntero de programa avanzado. */
static uint16_t rb_setup_col(uint8_t *ram, uint16_t HL, uint16_t iy, uint8_t E, uint8_t c)
{
    mwr(ram, iy + 0, (uint8_t)(mrd(ram, HL) + c));
    if (E & 0x08u) {                               /* BIT 3,E */
        mwr(ram, iy + 0, mrd(ram, iy + 0) | 0x40u);
        HL++; mwr(ram, iy + 1, mrd(ram, HL));
    }
    HL++;                                          /* 0x95D2 */
    uint16_t de = mrd16(ram, HL); HL = (uint16_t)(HL + 2);
    if ((mrd(ram, iy + 0) & 0x40u) == 0) {         /* BIT 6,(IY+0) */
        uint8_t A = mrd(ram, de); de++;
        if (A == 0) A = rb_spawn(ram, de, iy, &de); /* CALL Z 0x95ED */
        mwr(ram, iy + 1, A);
    }
    mwr(ram, iy + 2, de & 0xFFu); mwr(ram, iy + 3, (de >> 8) & 0xFFu);
    return HL;
}

/* sub 0x95A8: COMMAND HANDLER del stream del mapa. Programa N columnas del
 * bloque E2E0 (selector + tile-base + ptr) y dispara spawns de objetos. `hl`
 * = puntero al comando (ROM), `c` = tile base. Validado byte-exacto vs el
 * estado RAM completo de openMSX (incluye el spawn 0x9B22 en 0xE620). */
uint16_t z_map_command(uint8_t *ram, uint16_t hl, uint8_t c)
{
    uint8_t B = mrd(ram, hl); hl++;
    do {
        uint8_t A = (uint8_t)((mrd(ram, hl) & 0xF7u) << 2);   /* RES 3; *4 */
        uint16_t iy = (uint16_t)(0xE2E0u + A);
        uint8_t E = mrd(ram, hl); hl++;
        hl = rb_setup_col(ram, hl, iy, E, c);
    } while (--B);
    return hl;
}

/* sub 0x9888-0x9A67: REBUILD completo de una fila del scroll. Prólogo (arma
 * E2AE/E2B0/E2B2 desde 0xE702 + resetea IX/E71A), driver loop (4 entradas de
 * 0xE2C0), fetch (0x99D2) y expansor (z_map_expand). `ram` = RAM en 0xE000
 * (>= 0xC00 bytes). Validado byte-exacto vs el estado RAM completo de openMSX
 * (caso sin comando 0x95A8 ni recarga 0x95ED ni spawn 0x9B22). */
void z_map_rebuild(uint8_t *ram)
{
    /* prólogo 0x9888-0x98D2 */
    uint8_t a = mrd(ram, 0xE702u) & 0x03u;
    a = (uint8_t)((3u * a) << 3);
    mwr16(ram, 0xE2AEu, (uint16_t)(0xA444u + a));
    uint16_t de = (uint16_t)(((3u * (mrd(ram, 0xE702u) & 0x07u)) << 3) & 0xFFFFu);
    mwr16(ram, 0xE2B0u, (uint16_t)(0xA4A4u + de));
    mwr16(ram, 0xE2B2u, (uint16_t)(0xA564u + de));
    mwr(ram, IXB + 23, mrd(ram, IXB + 28));
    mwr(ram, IXB + 25, 0); mwr(ram, IXB + 24, 0);
    mwr16(ram, 0xE71Au, 0xEA40u);

    /* driver loop: 4 entradas de E2C0 (stride 8) */
    for (int k = 0; k < 4; k++) rb_driver_entry(ram, (uint16_t)(0xE2C0u + k * 8));

    /* fetch 0x99D2-0x99F5 */
    uint8_t col = mrd(ram, IXB + 25);
    if (col < 0x20u) {
        uint16_t ptr = mrd16(ram, 0xE2ACu + (mrd(ram, IXB + 23) & 7u) * 2u);
        uint16_t src = (uint16_t)(ptr + col);
        uint16_t d = mrd16(ram, 0xE71Au);
        for (uint16_t i = 0; i < (uint16_t)(0x20u - col); i++) mwr(ram, d++, rb((uint16_t)(src + i)));
    }

    /* expansor 0x99F7-0x9A67 (reusa la rutina ya validada) */
    z_map_expand(ram);
}

/* ==========================================================================
 * VM DE SCRIPT DE NIVEL (0x9405 init + 0x946E fill + dispatcher 0x94D1 +
 * fetch 0x97D5 + avance 0x97E3 + 13 handlers @ tabla 0x94EB). Genera el mapa
 * del nivel a medida que el scroll avanza. Validado byte-exacto: init + 24
 * pasos reproducen el buffer 0xE800 del nivel 1 (tools/sim_vm.py, 0/576).
 * Los handlers que NO tocan el mapa (sonido/sprite/score/dificultad) sólo
 * consumen sus operandos aquí; sus efectos externos (E1xx/VRAM) se portarán
 * con sus subsistemas. El handler 9 (salto de sección) queda pendiente.
 * ========================================================================== */

/* h2/h4 (0x9505/0x956C): arman N entradas del bloque E2C0. add=1 -> suma a +0 */
static uint16_t vm_h_e2c0(uint8_t *ram, uint16_t hl, int add)
{
    uint8_t B = mrd(ram, hl++);
    for (uint8_t i = 0; i < B; i++) {
        uint16_t iy = (uint16_t)(0xE2C0u + ((mrd(ram, hl++) << 3) & 0xFFu));
        if (add) mwr(ram, iy + 0, (uint8_t)(mrd(ram, iy + 0) + mrd(ram, hl++)));
        else     mwr(ram, iy + 0, mrd(ram, hl++));
        mwr(ram, iy + 1, mrd(ram, hl++));
        mwr(ram, iy + 2, mrd(ram, hl++));
        mwr(ram, iy + 3, mrd(ram, hl++));
        mwr(ram, iy + 6, 1); mwr(ram, iy + 7, 1);
    }
    return hl;
}

/* h1 (0x97B3): spawnea B objetos (0x45 + 3 bytes) en la tabla 0xE620. */
static uint16_t vm_h_spawn(uint8_t *ram, uint16_t hl)
{
    uint8_t B = mrd(ram, hl++);
    for (uint8_t i = 0; i < B; i++) {
        uint16_t slot;
        if (rb_slot_finder(ram, &slot)) { hl = (uint16_t)(hl + 3); }
        else { mwr(ram, slot++, 0x45u); for (int k = 0; k < 3; k++) mwr(ram, slot++, mrd(ram, hl++)); }
    }
    return hl;
}

/* Despacha un opcode del script. Devuelve el ptr avanzado (o 0xFFFF si el
 * handler no está portado / es salto de sección). */
static uint16_t vm_handler(uint8_t *ram, uint8_t idx, uint16_t hl)
{
    switch (idx) {
    case 0: {                                   /* 0x97A8 sonido (E12D) */
        uint8_t a = mrd(ram, hl++); mwr(ram, 0xE12Du, a);
        return (a & 0x04u) ? vm_h_spawn(ram, hl) : hl;   /* bit2 -> cae en h1 */
    }
    case 1:  return vm_h_spawn(ram, hl);        /* 0x97B3 */
    case 2:  return vm_h_e2c0(ram, hl, 0);      /* 0x9505 */
    case 3: {                                   /* 0x9537 mueve entradas E2 */
        uint8_t B = mrd(ram, hl++);
        for (uint8_t i = 0; i < B; i++) {
            uint16_t de = (uint16_t)(0xE200u | (((mrd(ram, hl++) << 3) + 0xC0u) & 0xFFu));
            uint16_t sh = (uint16_t)(0xE200u | (((mrd(ram, hl++) << 3) + 0xC0u) & 0xFFu));
            mwr(ram, de++, mrd(ram, sh)); mwr(ram, sh++, 0x80u);
            for (int k = 0; k < 7; k++) mwr(ram, de++, mrd(ram, sh++));
        }
        return hl;
    }
    case 4:  return vm_h_e2c0(ram, hl, 1);      /* 0x956C */
    case 5:  return z_map_command(ram, hl, 0);  /* 0x95A0 columnas E2E0 */
    case 6:  mwr(ram, 0xE71Cu, mrd(ram, hl)); return (uint16_t)(hl + 1);  /* 0x9678 */
    case 7: {                                   /* 0x9680 libera entradas E2C0 */
        uint8_t B = mrd(ram, hl++);
        for (uint8_t i = 0; i < B; i++) mwr(ram, (uint16_t)(0xE2C0u + ((mrd(ram, hl++) << 3) & 0xFFu)), 0x80u);
        return hl;
    }
    case 8:                                     /* 0x9699 sprite/score: 2 operandos */
        mwr16(ram, 0xE720u, mrd16(ram, hl)); mwr(ram, IXB + 29, 0); return (uint16_t)(hl + 2);
    case 10: mwr(ram, IXB + 35, mrd(ram, hl)); return (uint16_t)(hl + 1);  /* 0x96E5 VRAM */
    case 11: {                                  /* 0x9742 param + columna 0 */
        for (int i = 0; i < 4; i++) mwr(ram, (uint16_t)(0xE155u + i), mrd(ram, hl++));
        mwr(ram, 0xE154u, 0);
        mwr(ram, 0xE153u, rb((uint16_t)(0x976Cu + (mrd(ram, 0xE157u) & 0x1Fu))));
        return rb_setup_col(ram, hl, 0xE2E0u, 0, 0);
    }
    case 12: return (uint16_t)(hl + 1);         /* 0x977D dificultad: 1 operando */
    default: return 0xFFFFu;                     /* 9 (salto de sección) u otro: no portado */
    }
}

/* Un paso del scroll (0x94C3 -> 0x94D1): INC E702; ejecuta los comandos del
 * script vencidos; cuando el próximo no está vencido, avanza el buffer una
 * fila (0x97E3) y hace rebuild. */
void z_vm_step(uint8_t *ram)
{
    mwr16(ram, 0xE702u, (uint16_t)(mrd16(ram, 0xE702u) + 1));
    for (;;) {
        if (mrd16(ram, 0xE706u) != mrd16(ram, 0xE702u)) {   /* avance de fila 0x97E3 */
            uint8_t c = (uint8_t)(mrd(ram, IXB + 20) - 1);
            uint16_t hl;
            if (c & 0x80u) { c = 0x17u; hl = 0xEA28u; }
            else hl = (uint16_t)(mrd16(ram, 0xE715u) + 0xFFE8u);
            mwr(ram, IXB + 20, c); mwr16(ram, 0xE715u, hl);
            z_map_rebuild(ram);
            return;
        }
        uint16_t hl = mrd16(ram, 0xE704u);          /* opcode vencido 0x94DE */
        uint8_t op = mrd(ram, hl++); mwr(ram, IXB + 15, op);
        hl = vm_handler(ram, (uint8_t)(op & 0x0Fu), hl);
        if (hl == 0xFFFFu) return;                  /* handler no portado: corta */
        uint16_t trig = mrd16(ram, hl);             /* fetch siguiente 0x97D5 */
        mwr16(ram, 0xE704u, (uint16_t)(hl + 2)); mwr16(ram, 0xE706u, trig);
    }
}

/* Init de nivel (0x9405-0x9432): resetea bloques E2C0/E2E0 a 0x80, fija el
 * puntero de script y los triggers; luego corre 24 pasos (0x946E) para llenar
 * el buffer con las filas iniciales del mapa. `ram` debe venir en cero salvo
 * E701=0x01 y E712=0x34 (constantes de arranque de nivel). */
void z_level_init(uint8_t *ram, uint16_t script_ptr)
{
    for (int k = 0; k < 16; k++) mwr(ram, (uint16_t)(0xE2C0u + k * 4), 0x80u);
    uint16_t de = rb((script_ptr)) | (rb((uint16_t)(script_ptr + 1)) << 8);
    mwr16(ram, 0xE706u, de);
    mwr16(ram, 0xE702u, (uint16_t)(de - 1));
    mwr16(ram, 0xE704u, (uint16_t)(script_ptr + 2));
    mwr(ram, IXB + 0, mrd(ram, IXB + 0) & (uint8_t)~0x01u);
    for (int i = 0; i < 0x18; i++) z_vm_step(ram);   /* 0x946E: llena 24 filas */
}

/* sub_5C10: copia un stream terminado en 0x00 desde ROM[src] vía emit().
 * (textos de la name table: créditos, HUD). Devuelve el src final. */
uint16_t z_copy_literal(uint16_t src, void (*emit)(void *, uint8_t), void *ctx)
{
    for (;;) {
        uint8_t b = rb(src++);
        if (b == 0u) break;
        emit(ctx, b);
    }
    return src;
}

/* Descomprime desde ROM[src]; cada byte de salida va por emit(ctx, byte).
 * Devuelve el src final (tras el comando FIN). */
uint16_t z_decompress(uint16_t src, void (*emit)(void *, uint8_t), void *ctx)
{
    uint8_t esc = 0xFFu;
    uint8_t flag = 0u;
    for (;;) {
        uint8_t b = rb(src++);
        if (b != esc) {                       /* literal (con cuenta de flag) */
            int c = (flag & 1u) ? cnt256(rb(src++)) : 1;
            while (c--) emit(ctx, b);
            continue;
        }
        {
            uint8_t b2 = rb(src++);
            if (b2 != esc) {                  /* ESC simple: alterna el flag */
                src--;                        /* devuelve b2 */
                flag ^= 1u;
                continue;
            }
        }
        {                                     /* ESC ESC cmd */
            uint8_t cmd = rb(src++);
            if (cmd == 0u) break;             /* FIN */
            if (cmd == 1u) { esc = rb(src++); continue; }  /* nuevo escape */
            if (cmd == 2u) {                  /* repetir bloque */
                int C = cnt256(rb(src++));
                uint16_t blk = src;
                while (C--) {
                    src = blk;
                    int B = cnt256(rb(src++));
                    while (B--) {
                        uint8_t a = rb(src++);
                        int c = (flag & 1u) ? cnt256(rb(src++)) : 1;
                        while (c--) emit(ctx, a);
                    }
                }
                continue;
            }
            /* cmd desconocido: no debería pasar con datos válidos */
            break;
        }
    }
    return src;
}
