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
