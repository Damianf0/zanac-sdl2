#ifndef ZANAC_GFX_H
#define ZANAC_GFX_H
#include <stdint.h>

/* sub_5CDC: descompresor RLE anidado de Zanac. Descomprime desde ROM[src]
 * (dirección Z80) emitiendo cada byte de salida por emit(ctx, byte).
 * Devuelve el src final. Validado byte a byte vs openMSX. */
uint16_t z_decompress(uint16_t src, void (*emit)(void *, uint8_t), void *ctx);

/* sub_5C10: copia literal terminada en 0x00 desde ROM[src]. */
uint16_t z_copy_literal(uint16_t src, void (*emit)(void *, uint8_t), void *ctx);

/* sub_9A80: blit del buffer circular del mapa (24×24) al playfield de la
 * name table (32-wide), desde la fila `start` con wrap. */
void z_blit_playfield(const uint8_t *buf, int start, uint8_t *nt);

/* sub 0x99D2-0x99F5: fetch de fila de mapa cruda desde el segmento ROM
 * seg_tbl[ix23&7] + col(=ix25) al staging; copia (0x20-col) bytes (0 si
 * col>=0x20). Validado 32/32 vs openMSX. */
uint16_t z_map_fetch(const uint16_t seg_tbl[8], uint8_t ix23, uint8_t ix25,
                     uint8_t *staging);

/* sub 0x99FD-0x9A67: expansor de runs del scroll. Procesa las 8 columnas de
 * 0xE2E0, expande sus programas (ROM) al staging y copia 24 bytes al buffer
 * visible en (0xE715). `ram` = RAM mapeada en 0xE000 (>= 0xC00 bytes).
 * Validado byte-exacto vs estado RAM de openMSX. */
void z_map_expand(uint8_t *ram);

#endif

