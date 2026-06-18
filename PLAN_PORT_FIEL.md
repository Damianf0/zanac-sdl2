# Plan — Port fiel de ZANAC (Compile / Pony Canyon, 1986) desde el disasm

Mismo método que el port de **The Castle** (del cual este proyecto hereda
la infraestructura): reconstruir el motor **función por función desde el
desensamblado de la ROM**, validando cada sistema **contra openMSX** como
oráculo. Ninguna heurística nueva: lo que no se entiende se traza en openMSX
y se porta del disasm.

> Zanac es un **shoot'em-up de scroll vertical en tiempo real** — mucho más
> grande que The Castle (scroll suave, decenas de enemigos/disparos
> simultáneos, IA adaptativa "ALC", armas, jefes). El enfoque es idéntico;
> el alcance, mayor.

---

## Fase 0 — Fundación ✅ (2026-06-17)

- **ROM**: `zanac.rom` (32 KB, cartucho MSX plano; header `AB`, INIT 0x4010).
  Sin mapper — mapea fijo en 0x4000-0xBFFF.
- **Desensamblador propio** `tools/z80dis.py`: descenso recursivo desde el
  INIT + STATEMENT del header, separando código de datos. **Validado contra
  el desensamblador de openMSX** (`tools/dis_oracle.tcl` + comparación de
  longitudes): **424/424 instrucciones coinciden** en el primer rango.
- **Disasm inicial** `zanac_disasm.asm`: ~3 KB de código alcanzado por el
  descenso estático (crecerá al portar — los saltos indirectos/tablas
  revelan más código). La rutina INIT decodifica limpia: `DI; IM 1`, gancho
  de interrupción en 0xFD9A (HKEYI ← JP 0x43DA), `LD SP,0xF000`, limpieza de
  RAM 0xE000-0xE7FF.
- **Oráculo openMSX** operativo (`tools/cap_screen.tcl`): confirma que Zanac
  corre en **SCREEN 2 (Graphics II) con sprites 16×16** — el MISMO modo de
  video que The Castle. R2=0x0E (name 0x3800), R4=0x03 (pattern 0x1800),
  R5=0x77 (sprite attr 0x3B80), R6=0x03 (sprite pat 0x1800).

---

## Infraestructura a reusar de The Castle

- `hal_sdl2.c` / `hal.h`: emulación VDP TMS9918A (SCREEN 2) + PSG AY-3-8910 +
  input + timing. Hay que **genericar** (quitar deps de The Castle:
  `geom.h`/`game.h`, `g_actors_on`, `debug_draw_geom`).
- Patrón de tests (`tests/run_tests.py`) + harness por env-vars + oráculos
  tcl de openMSX (capturas byte/frame/registro-exactas).
- `build.ps1` (MinGW-w64 + SDL2).
- Control de volumen (F10-F12) y el esquema de cheats de QA (F5-F9).

---

## Fases (roadmap, a refinar al avanzar)

### Fase 1 — Arranque + VDP fiel ← EN CURSO
Portar el INIT (0x4010) y la inicialización de pantalla: modo SCREEN 2,
carga de tiles/patrones a VRAM, paleta. Objetivo: la **pantalla de título**
byte-idéntica a openMSX (fixture de VRAM, como `vram_title` de The Castle).

Avance (2026-06-17):
- HAL genericado (sin deps de The Castle) + `build.ps1` + `main.c` esqueleto:
  carga la ROM, inicializa el HAL en SCREEN 2 con los registros VDP reales
  de Zanac y presenta frames. **Compila y corre** (zanac.exe 79 KB; smoke
  headless CASTLE_FAST OK) — la infraestructura reusada funciona.
- Boot mapeado: INIT (0x4010) instala el gancho de interrupción (HKEYI ←
  0x43DA), stack 0xF000, limpia RAM 0xE000-0xE7FF, y llama una cadena de
  init (L4E45, L513F, L516C, L428A, L5A11, L41DB, L5BEC, L42E2...).
  `L4E45` = gestión de SLOTS MSX (RSLREG/ENASLT) → SE IGNORA en el port C.
- PENDIENTE: ubicar la carga de VRAM (tiles/patrones/name table) y portar
  el render del título; comparar VRAM byte a byte vs openMSX.

### Fase 2 — Scroll vertical + mapa de nivel
El corazón de Zanac. Cómo se almacena el mapa de fondo, cómo scrollea
(probable reescritura de la name table por filas + registro de scroll fino),
y el ritmo del scroll. Trazar en openMSX el patrón de escritura a VRAM por
frame.

### Fase 3 — Jugador (nave): movimiento + disparo
Input, límites, sprite, disparo principal y la rotación de armas
secundarias (Zanac tiene 8 armas). Validar posición/sprites frame a frame.

### Fase 4 — Enemigos + proyectiles + IA adaptativa (ALC)
El sistema de enemigos (spawns por scroll), proyectiles, colisiones, y la
famosa lógica de dificultad adaptativa. El más grande.

### Fase 5 — Jefes, ítems, score, vidas, HUD, game over.

### Fase 6 — Música/PSG verificada (registro a registro vs openMSX).

---

## Reglas (heredadas de The Castle)

1. Ninguna heurística nueva. Lo que no se entiende, se traza y se porta.
2. Las capturas de openMSX son SOLO oráculo de tests, nunca datos del runtime.
3. Antes de commitear: la suite de tests en verde.
4. Build canónico: `build.ps1` (MinGW; CMake no está instalado).
