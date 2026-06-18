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

/* ==========================================================================
 * Carga de GRÁFICOS del título (patrones + sprites + color) — la receta de
 * SETWRT + descompresión capturada de la orquestación real (trace_orch.tcl):
 *   patrón 3 tercios ← 5EFC ; sprites 0x1800 ← 6976 ; color 3 tercios ← 64D3 ;
 *   overlay del logo (patrón +0x580 ← 5D2C ; color +0x580 ← 5EF0).
 * (La name table = copias literales + tabla 0x4827, próximo incremento.)
 * ========================================================================== */
typedef struct { uint16_t addr; } VramCtx;
static void emit_vram(void *ctx, uint8_t b)
{
    VramCtx *c = (VramCtx *)ctx;
    hal_vdp_write_vram(c->addr++, b);
}

static void load_title_gfx(void)
{
    VramCtx c;
    for (int t = 0; t < 3; t++) { c.addr = (uint16_t)(t * 0x800);
        z_decompress(0x5EFCu, emit_vram, &c); }                 /* patrones  */
    c.addr = 0x1800u; z_decompress(0x6976u, emit_vram, &c);     /* sprites   */
    for (int t = 0; t < 3; t++) { c.addr = (uint16_t)(0x2000 + t * 0x800);
        z_decompress(0x64D3u, emit_vram, &c); }                 /* color     */
    for (int t = 0; t < 3; t++) { c.addr = (uint16_t)(0x0580 + t * 0x800);
        z_decompress(0x5D2Cu, emit_vram, &c); }                 /* logo pat  */
    for (int t = 0; t < 3; t++) { c.addr = (uint16_t)(0x2580 + t * 0x800);
        z_decompress(0x5EF0u, emit_vram, &c); }                 /* logo col  */
}

/* Name table: base de espacios + los 8 textos (créditos/HUD) por copia
 * literal 0x00-term (L5C10). Dest/src capturados de la orquestación real
 * (trace_nt2.tcl). Pendiente del byte-exacto: el fondo del LOGO (tiles
 * 0xB0-0xDE) y los dígitos del SCORE, que el juego arma por una vía aparte
 * (copia base por LDIRVM/FILVRM del BIOS + render de score). */
static const struct { uint16_t dst, src; } title_text[8] = {
    {0x3803, 0x5A2A}, {0x3811, 0x5A36}, {0x39E3, 0x5ACE}, {0x3A03, 0x5AED},
    {0x3A23, 0x5B08}, {0x3A43, 0x5B29}, {0x3A8E, 0x5B4A}, {0x3AAE, 0x5B54},
};
static void load_title_nametable(void)
{
    VramCtx c;
    for (uint16_t a = 0x3800u; a < 0x3B00u; a++) hal_vdp_write_vram(a, 0x20u);
    for (int i = 0; i < 8; i++) {
        c.addr = title_text[i].dst;
        z_copy_literal(title_text[i].src, emit_vram, &c);
    }
}

/* Harness: ZANAC_TITLEGFX=out.bin → limpia VRAM, carga los gráficos del
 * título y vuelca VRAM 0x0000-0x37FF (patrones+sprites+color) para comparar
 * contra tests/fixtures/vram_title.bin. */
static int titlegfx_harness(const char *out)
{
    FILE *f = fopen(out, "wb");
    if (!f) return 1;
    for (uint16_t a = 0; a < 0x3B00u; a++) hal_vdp_write_vram(a, 0u);  /* clear */
    load_title_gfx();
    load_title_nametable();
    for (uint16_t a = 0; a < 0x3B00u; a++) {
        uint8_t b = hal_vdp_read_vram(a);
        fwrite(&b, 1, 1, f);
    }
    fclose(f);
    printf("ZANAC_TITLEGFX -> %s\n", out);
    return 0;
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
        const char *tg = getenv("ZANAC_TITLEGFX");
        if (tg) { int r = titlegfx_harness(tg); free(rom); return r; }
        /* ZANAC_BLIT=out.bin + ZANAC_BLITBUF=buf.bin + ZANAC_BLITSTART=N:
         * corre z_blit_playfield sobre el buffer dado y vuelca la name table
         * (768B). Valida el blit del scroll contra openMSX. */
        const char *bl = getenv("ZANAC_BLIT");
        if (bl) {
            const char *bf = getenv("ZANAC_BLITBUF");
            int start = getenv("ZANAC_BLITSTART") ? atoi(getenv("ZANAC_BLITSTART")) : 0;
            uint8_t buf[24*24], nt[768];
            FILE *bi = bf ? fopen(bf, "rb") : NULL;
            if (!bi || fread(buf, 1, sizeof buf, bi) != sizeof buf) { free(rom); return 1; }
            fclose(bi);
            memset(nt, 0, sizeof nt);
            z_blit_playfield(buf, start, nt);
            FILE *o = fopen(bl, "wb");
            if (o) { fwrite(nt, 1, sizeof nt, o); fclose(o); }
            printf("ZANAC_BLIT -> %s (start=%d)\n", bl, start);
            free(rom); return 0;
        }
        /* ZANAC_MAPFETCH=out.bin + ZANAC_MF_TBL="p0,p1,..,p7" (hex) +
         * ZANAC_MF_IX23 + ZANAC_MF_IX25: corre z_map_fetch y vuelca el
         * staging (32B). Valida el fetch de fila de mapa contra openMSX. */
        const char *mf = getenv("ZANAC_MAPFETCH");
        if (mf) {
            uint16_t tbl[8] = {0};
            const char *ts = getenv("ZANAC_MF_TBL");
            if (ts) { char b[256]; strncpy(b, ts, sizeof b - 1); b[sizeof b - 1] = 0;
                int i = 0; for (char *t = strtok(b, ","); t && i < 8; t = strtok(NULL, ","))
                    tbl[i++] = (uint16_t)strtol(t, NULL, 16); }
            uint8_t ix23 = getenv("ZANAC_MF_IX23") ? (uint8_t)strtol(getenv("ZANAC_MF_IX23"), NULL, 16) : 0;
            uint8_t ix25 = getenv("ZANAC_MF_IX25") ? (uint8_t)strtol(getenv("ZANAC_MF_IX25"), NULL, 16) : 0;
            uint8_t staging[32];
            memset(staging, 0, sizeof staging);
            z_map_fetch(tbl, ix23, ix25, staging);
            FILE *o = fopen(mf, "wb");
            if (o) { fwrite(staging, 1, sizeof staging, o); fclose(o); }
            printf("ZANAC_MAPFETCH -> %s\n", mf);
            free(rom); return 0;
        }
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
