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
- TÍTULO capturado y caracterizado (oráculo): `tests/fixtures/vram_title.bin`
  (16 KB, estable a t=6s) + `vdp_title.txt`. SCREEN 2: patrones 0x0000-17FF,
  color 0x2000-37FF, name 0x3800. El título NO es un bitmap full-screen:
  es una pantalla TILEADA — texto por FUENTE (name table usa códigos ASCII:
  "SCORE...0" = 0x53,0x43,0x4F...) + tiles de logo (corrida 0xD5-0xDC). 87
  tiles distintos. Los patrones/color NO están crudos en la ROM.
- CARGADOR ubicado (dinámico, tools/trace_vdpwr.tcl — histograma de PC que
  escriben al puerto VDP 0x98 durante el boot):
  * 0x23CA (BIOS): clear de 16 KB de VRAM al arranque.
  * **0x5C00 (cart): primitivas de escritura a VRAM** — L5C07 = `OUT(C),A`
    (BC=(0x0007)=puerto 0x98); L5C10 = copia un stream terminado en 0x00
    desde (HL) a VRAM (L5BFC = variante con DI). 21866+5182 escrituras: el
    grueso del título pasa por acá.
  * 0x02A5/0x02E5 (BIOS LDIRVM): copian buffers RAM→VRAM.
  * **0x046D (BIOS): 768 bytes = la NAME TABLE** completa (un LDIRVM).
- FUENTE trazada (tools/trace_src.tcl): el loader lee HL **directo de la ROM
  del cartucho**, rango 0x4827-0x70B6 (no hay buffer RAM intermedio para el
  grueso). 27048 escrituras.
- **DESCOMPRESOR ubicado y desensamblado** (tools/trace_caller.tcl →
  retorno 0x5D28; disasm seedeado en zanac_disasm.asm, 0x5CDC-0x5D2B):
  RLE ANIDADO con escape. Registros: D = byte-marcador (escape), E bit0 =
  flag "run con cuenta explícita", HL = puntero al stream en ROM.
  * L5CDD (loop): A=(HL); si A==D → escape; si no → CALL L5D1A (emite A).
  * Escape simple (un D): toggle E bit0 (alterna cuenta 1 ↔ cuenta del stream).
  * D D <a>: CALL L5C2E = referencia vía TABLA DE WORDS INLINE (idiom
    EX(SP),HL) — salta a un sub-stream.
  * L5D06: run anidado (C=cuenta externa, B=interna, A=valor) → L5D1A.
  * L5D1A: emite A vía L5C07 (OUT 0x98); B=1 o B=(HL) según E bit0.
- **DESCOMPRESOR PORTADO A C Y VALIDADO ✅ (2026-06-17)** — `gfx.c`
  (`z_decompress`): el algoritmo completo (escape/toggle, tabla de comandos
  inline FF FF 0/1/2, run anidado, cuenta 0=256 por DJNZ). 13 invocaciones
  del título (params de tools/trace_entry.tcl: src ∈ {5EFC,6976,64D3,5D2C,
  5EF0}, ESC=FF, flag=0). Produce **17264/17264 bytes idénticos** a openMSX
  (tools/trace_out.tcl → tests/fixtures/decomp_title.txt). Suite Zanac
  nueva (tests/run_tests.py), 1/1.
- **GRÁFICOS DEL TÍTULO PORTADOS Y VALIDADOS ✅ (2026-06-17)** — receta
  capturada (tools/trace_orch.tcl): patrón 3 tercios ← 5EFC, sprites 0x1800
  ← 6976, color 3 tercios ← 64D3, overlay logo (patrón +0x580 ← 5D2C, color
  +0x580 ← 5EF0). `load_title_gfx()` en main.c reproduce la VRAM
  **byte-idéntica** en patrones (0x0000-17FF), sprites (0x1800-1FFF) y color
  (0x2000-37FF) = 14336 bytes. Confirmado: los 3 tercios son idénticos (el
  descompresor reescribe la misma data). Suite Zanac 2/2.
- **NAME TABLE: texto porteado (689/768) ✅ (2026-06-18)** — copia literal
  L5C10 portada (`z_copy_literal` en gfx.c) + los 8 textos de crédito/HUD
  capturados (trace_nt2.tcl): SCORE, TOP, "GAME DESIGN BY COMPILE",
  "PRODUCED BY AAI", "PRESENTED BY PONY INC.", "COPYRIGHT @ 1986 PONY INC.".
  `load_title_nametable()`: base de espacios + los 8 textos.
- PENDIENTE (79 bytes del título): el FONDO del logo (tiles 0xB0-0xDE en
  0x38A8/0x38CA/0x38E9/0x3908/0x3969) y los dígitos del SCORE (0 / 10000).
  El juego los arma por una vía aparte: el clear es FILVRM (0x800 desde
  0x3800), y el contenido base lo escribe el loop LDIRVM del BIOS (pc 0x02A5)
  — el rastreo a nivel registro en internals del BIOS es turbio. Quedó
  trazada toda la tubería; falta ubicar la fuente base + el render de score.
  Decisión: no es bloqueante (es el logo/HUD del título); se puede cerrar
  después o saltar a Fase 2 (scroll, el juego real).
- INFRA: z80dis.py ahora acepta `--seed 0xADDR` para entradas alcanzadas por
  saltos indirectos/tablas (como el descompresor).

### Fase 2 — Scroll vertical + mapa de nivel ← EN CURSO
El corazón de Zanac.

MECANISMO DESCUBIERTO (2026-06-18, tools/probe_scroll*.tcl, openMSX):
- El scroll es **por SOFTWARE reescribiendo la NAME TABLE** (TMS9918 SCREEN 2
  no tiene registro de scroll). En 2s de gameplay: name table = 11907
  escrituras (~99/frame), sprite-attr = 2880 (~24/frame), **patrón/color = 0**
  (los tiles quedan fijos, cargados una vez).
- Granularidad de **TILE (8px)**: observando la columna 0 en frames
  consecutivos, todo el contenido se desplaza 1 fila hacia abajo (el mapa
  baja hacia la nave) cada ~5 frames; el checksum cambia → entra mapa NUEVO
  arriba (es una ventana a un mapa vertical más grande, no un ciclo estático).
- La name table es entonces una VENTANA al mapa; cada paso desplaza filas y
  escribe la fila nueva desde los datos del mapa.

RENDER DEL SCROLL MAPEADO (2026-06-18, probe_scrollpc/mapbuf):
- **0xE800 = buffer del mapa en RAM** (la ventana del playfield, filas de
  24 tiles = 24 cols de ancho; el panel lateral del HUD ocupa cols 24-31).
  VERIFICADO: 0xE800.. espeja exactamente la name table del playfield
  (desfasado por la fila de scroll vigente).
- **Rutina de blit 0x9A80** (escritor 0x9AB6, ~99 wr/frame): SETWRT(0x3800
  + fila*0x20); copia 24 bytes desde (DE=0xE800+...) por OUT(0x98); avanza
  fila. Dibuja A filas (A = 0x19 - IX[0x14], el contador de filas a
  refrescar). Hay un camino "split" (0x9AC5, usa IY=0xE180 con offset
  por fila en IY+24) para el borde donde el buffer circular envuelve.
- Modelo del scroll: el motor actualiza 0xE800 (lo desplaza + mete filas
  nuevas del mapa de nivel) y esta rutina lo blittea a VRAM.

PENDIENTE (núcleo de Fase 2): el MOTOR que llena/desplaza 0xE800 desde el
mapa de nivel en ROM — ubicar el mapa y su formato (¿comprimido con
z_decompress?), la variable de posición/scroll, y el ritmo. Después portar
el blit (0x9A80) + el motor y validar la name table frame a frame vs openMSX.

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
