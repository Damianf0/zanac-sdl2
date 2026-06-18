/*
 * THE CASTLE — HAL (Hardware Abstraction Layer) public interface
 * ==============================================================
 * Este header es el único punto de contacto entre la lógica del juego
 * (the_castle.c) y cualquier implementación de plataforma (hal_sdl2.c,
 * hal_wasm.c, hal_null.c, …).
 *
 * Agregar una nueva plataforma = implementar todas las funciones de abajo.
 */

#pragma once
#ifndef CASTLE_HAL_H
#define CASTLE_HAL_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==========================================================================
 * CICLO DE VIDA
 * ========================================================================== */

/**
 * hal_init() — Inicializa toda la plataforma.
 * @param pal_timing  true=50Hz (PAL), false=60Hz (NTSC)
 * @return true si todo fue bien, false si algo falló.
 */
bool hal_init(bool pal_timing);

/**
 * hal_quit() — Libera todos los recursos de plataforma.
 */
void hal_quit(void);

/**
 * hal_is_running() — Consulta si el usuario no ha pedido cerrar.
 * A diferencia de hal_poll_events(), no procesa eventos. Útil para
 * comprobar en loops que no pueden consumir el evento en ese momento.
 */
bool hal_is_running(void);

/**
 * hal_poll_events() — Procesa eventos del sistema (input, ventana, etc.).
 * Debe llamarse una vez por frame, antes de leer el joystick.
 * @return false si el usuario pidió cerrar la aplicación.
 */
bool hal_poll_events(void);

/* ==========================================================================
 * VDP — Video Display Processor (TMS9918A)
 * ========================================================================== */

/** Escribe un registro VDP (R0..R7). */
void    hal_vdp_write_reg(uint8_t reg, uint8_t val);

/** Escribe un byte en VRAM. */
void    hal_vdp_write_vram(uint16_t addr, uint8_t val);

/** Lee un byte de VRAM. */
uint8_t hal_vdp_read_vram(uint16_t addr);

/** Rellena un bloque de VRAM con un valor (equivale a FILVRM). */
void    hal_vdp_fill_vram(uint16_t addr, uint8_t val, uint16_t count);

/** Copia datos de RAM a VRAM (equivale a LDIRVM). */
void    hal_vdp_copy_to_vram(uint16_t dst, const uint8_t *src, uint16_t count);

/** Copia datos de VRAM a RAM (equivale a LDIRMV). */
void    hal_vdp_copy_from_vram(uint16_t src, uint8_t *dst, uint16_t count);

/** Configura el VDP en modo Screen 2 / Graphics II (equivale a INIGRP). */
void    hal_vdp_init_screen2(void);

/** Apaga la pantalla (equivale a DISSCR). */
void    hal_vdp_disable_screen(void);

/** Borra todos los sprites (equivale a CLRSPR). */
void    hal_vdp_clear_sprites(void);

/**
 * hal_vdp_present() — Renderiza el estado actual de VRAM y lo muestra.
 * Llamado automáticamente por hal_wait_vsync(), pero puede llamarse
 * manualmente si se necesita un flush inmediato.
 */
void    hal_vdp_present(void);

/* Guarda el framebuffer actual como BMP (debug/screenshot). */
void    hal_screenshot(const char *path);

/* ==========================================================================
 * PSG — Programmable Sound Generator (AY-3-8910)
 * ========================================================================== */

/** Escribe un registro PSG (R0..R15) — equivale a BIOS WRTPSG. */
void    hal_psg_write(uint8_t reg, uint8_t val);

/** Lee un registro PSG — equivale a BIOS RDPSG. */
uint8_t hal_psg_read(uint8_t reg);

/** Activa/desactiva el log de escrituras PSG (validación de música,
 *  harness sin SDL). f=NULL desactiva. Formato: "reg val\n" por escritura. */
void    hal_psg_log_set(void *f);

/* ==========================================================================
 * INPUT
 * ========================================================================== */

/**
 * hal_joystick_read() — Lee la dirección del joystick.
 * @param port  0 = joystick 1, 1 = joystick 2
 * @return Dirección (0-8) igual que BIOS GTSTCK:
 *         0=nada, 1=↑, 2=↑→, 3=→, 4=↓→, 5=↓, 6=↓←, 7=←, 8=↑←
 */
uint8_t hal_joystick_read(uint8_t port);

/**
 * hal_key_pressed() — ¿Está pulsado el botón de acción (fire/space)?
 * Equivale a BIOS GTTRIG para el botón 1 del joystick 1.
 */
bool    hal_key_pressed(void);

/**
 * hal_any_key() — ¿hay alguna tecla del teclado apretada? (la demo del
 * juego se corta con cualquier tecla de la matriz, 0x62E8).
 */
bool    hal_any_key(void);

/* Volumen maestro de salida (0..8, 0=mudo). Controles de QA por F10-F12,
 * fuera del modelo PSG. */
void    hal_audio_vol_up(void);
void    hal_audio_vol_down(void);
void    hal_audio_mute_toggle(void);
int     hal_audio_vol(void);

/**
 * hal_cheat_keys() — bitmask de las teclas de CHEAT de QA (F5-F9):
 *   bit0 F5 god, bit1 F6 llaves, bit2 F7 mapa, bit3 F8 sala--, bit4 F9 sala++.
 */
uint8_t hal_cheat_keys(void);

/* Modo actores/interactivo (lo consume el render del VDP y los efectos
 * bloqueantes del motor). Definido en hal_sdl2.c. */
extern int g_actors_on;

/**
 * hal_msx_keyrow6() — Fila 6 de la matriz de teclado MSX, activo-bajo
 * (bit0=SHIFT, bit1=CTRL, bit2=GRAPH, bit3=CAPS, bit5=F1, bit6=F2, bit7=F3).
 * El juego la lee acumulada en (0xEAD3) y decide la velocidad en 0x62FA:
 * CTRL = correr, CTRL+GRAPH = turbo. Host: CTRL→CTRL, ALT→GRAPH.
 */
uint8_t hal_msx_keyrow6(void);

/* ==========================================================================
 * TIMING
 * ========================================================================== */

/**
 * hal_wait_vsync() — Espera al VBlank y presenta el frame.
 * El juego llama a esta función al final de cada frame.
 * La implementación debe: renderizar VRAM → mostrar → esperar hasta
 * completar el periodo de frame (16.67 ms a 60Hz / 20 ms a 50Hz).
 */
void    hal_wait_vsync(void);

/**
 * hal_delay() — Espera N frames completos (útil para pausas en cutscenes).
 */
void    hal_delay(uint8_t frames);

/**
 * hal_wait_game_frame() — Espera `ms` milisegundos en unidades de VBlank
 * (acumulador fraccional: la media converge a `ms` exactos y la música
 * sigue tickeando a 60 Hz). El juego real pacea el loop con el busy-wait
 * de sub_5128 (EACA × sub_50E8), no con el VBlank.
 */
void    hal_wait_game_frame(double ms);

#ifdef __cplusplus
}
#endif

#endif /* CASTLE_HAL_H */
