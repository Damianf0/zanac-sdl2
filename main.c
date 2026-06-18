/*
 * ZANAC (Compile / Pony Canyon, 1986) — Port fiel a C + SDL2
 * ===========================================================
 * Reconstrucción función por función desde zanac_disasm.asm, validada contra
 * openMSX. Hereda la infraestructura (HAL VDP/PSG/input) del port de The
 * Castle.
 *
 * Estado: Fase 1 (arranque + VDP). Por ahora el esqueleto carga la ROM,
 * inicializa el HAL en SCREEN 2 con los registros VDP reales de Zanac
 * (capturados de openMSX) y presenta frames. El contenido de pantalla
 * (tiles + title) se porta a continuación desde la cadena de init del INIT
 * (L4E45 / L513F / L516C ...).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <SDL2/SDL.h>

#include "hal.h"
#include "gfx.h"

#define ROM_SIZE 32768u
#define ROM_PATH "zanac.rom"

const uint8_t *g_rom = NULL;     /* ROM mapeada en 0x4000-0xBFFF */
uint32_t       g_rom_size = 0;

/* Hook de música en VBlank (lo llama hal_wait_vsync). Stub hasta portar
 * la música de Zanac. */
void music_isr_tick(void) { }

/* lectura de la ROM por dirección Z80 (0x4000-0xBFFF) */
static uint8_t rom_rb(uint16_t addr)
{
    uint32_t off = (uint32_t)addr - 0x4000u;
    return (g_rom && off < g_rom_size) ? g_rom[off] : 0xFFu;
}

static uint8_t *load_rom(const char *path, uint32_t *size_out)
{
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "Error: no se pudo abrir '%s'\n", path); return NULL; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); rewind(f);
    uint8_t *buf = malloc((size_t)sz);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { free(buf); fclose(f); return NULL; }
    fclose(f);
    if (buf[0] != 0x41 || buf[1] != 0x42)
        fprintf(stderr, "Aviso: magic MSX incorrecto (0x%02X%02X)\n", buf[0], buf[1]);
    *size_out = (uint32_t)sz;
    printf("ROM '%s' cargada (%u bytes), INIT=0x%04X\n",
           path, *size_out, (unsigned)(buf[2] | (buf[3] << 8)));
    return buf;
}

/* Registros VDP reales de Zanac al iniciar (capturados de openMSX,
 * tools/cap_screen.tcl): SCREEN 2 (Graphics II) con sprites 16x16. */
static void vdp_init_zanac(void)
{
    static const uint8_t regs[8] = {
        0x02, 0x62, 0x0E, 0xFF, 0x03, 0x77, 0x03, 0x01
    };
    for (uint8_t r = 0; r < 8; r++) hal_vdp_write_reg(r, regs[r]);
}

/* Harness de validación del descompresor (sin SDL): ZANAC_DECOMP=out.txt
 * corre las 13 invocaciones del título (mismos punteros fuente que capturó
 * tools/trace_entry.tcl) y vuelca cada byte de salida — comparable contra
 * tools/trace_out.tcl (la salida real de openMSX). */
static void emit_file(void *ctx, uint8_t b) { fprintf((FILE *)ctx, "%02X\n", b); }

static int decomp_harness(const char *out)
{
    static const uint16_t calls[13] = {
        0x5EFC, 0x5EFC, 0x5EFC, 0x6976, 0x64D3, 0x64D3, 0x64D3,
        0x5D2C, 0x5D2C, 0x5D2C, 0x5EF0, 0x5EF0, 0x5EF0
    };
    FILE *f = fopen(out, "w");
    if (!f) return 1;
    for (int i = 0; i < 13; i++) z_decompress(calls[i], emit_file, f);
    fclose(f);
    printf("ZANAC_DECOMP -> %s\n", out);
    return 0;
}

int main(int argc, char *argv[])
{
    const char *rom_path = (argc > 1) ? argv[1] : ROM_PATH;
    uint32_t rom_size = 0;
    uint8_t *rom = load_rom(rom_path, &rom_size);
    if (!rom) return 1;
    g_rom = rom; g_rom_size = rom_size;

    {
        const char *dc = getenv("ZANAC_DECOMP");
        if (dc) { int r = decomp_harness(dc); free(rom); return r; }
    }

    if (!hal_init(false)) { free(rom); return 1; }
    hal_vdp_init_screen2();
    hal_vdp_clear_sprites();
    vdp_init_zanac();

    printf("Zanac — Fase 1 (esqueleto VDP). Esc para salir.\n");

    /* loop principal: por ahora solo presenta el frame (pantalla en el
     * backdrop). El render de tiles/title se agrega al portar la cadena de
     * init. Headless/smoke con CASTLE_FAST=1 sale tras unos frames. */
    int fast_frames = getenv("CASTLE_FAST") ? 120 : -1;
    while (hal_poll_events()) {
        hal_vdp_present();
        hal_wait_vsync();
        if (fast_frames > 0 && --fast_frames == 0) break;
    }

    hal_quit();
    free(rom);
    (void)rom_rb;   /* lo usará el port del init/video */
    return 0;
}
