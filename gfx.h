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

#endif

