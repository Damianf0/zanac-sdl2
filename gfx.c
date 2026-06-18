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
