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
  PENDIENTE: portar el descompresor a C, ubicar sus call-sites y los params
  (D/E/HL/dest VRAM) por cada sección (patrones/color/name), y comparar VRAM
  byte a byte (suite `vram_title`, como en The Castle).
- INFRA: z80dis.py ahora acepta `--seed 0xADDR` para entradas alcanzadas por
  saltos indirectos/tablas (como el descompresor).

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
