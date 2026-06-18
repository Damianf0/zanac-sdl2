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

TUBERÍA COMPLETA DEL SCROLL MAPEADA (2026-06-18, probe_mapfill):
1. **Fill de filas nuevas** (PC 0x99F6, 672 wr): copia el mapa de nivel al
   buffer (DE=0xEA40 = 0xE800+0x240 = fila de staging). El mapa está en
   **ROM (~0xA564), tile data CRUDA** (verificado byte a byte). PERO el
   acceso NO es lineal: usa una **tabla de indirección en 0xE2AC** (words,
   indexada por IX[23]&7) + RST 0x20 + LDIR de (0x20-C) bytes, con filas de
   32 de ancho. Es el formato de mapa de Zanac (segmentos por tabla); el run
   crudo de 0xA564 era un segmento contiguo. FALTA decodificar 0xE2AC.
2. **Shift del scroll** (PC 0x9A66, 504 wr): copia buffer→buffer
   (0xEA48→0xE968) — desplaza las filas existentes.
3. **Blit a VRAM** (0x9A80): buffer 0xE800 → name table 0x3800 (ya mapeado).

FORMATO DE MAPA DECODIFICADO (2026-06-18, probe_rst20/dump_ram):
- El juego corre parte de su runtime desde **RAM página 0** y replica los
  vectores RST del BIOS ahí: **RST 0x20 (→0x11C6) = DCOMPR** (CP HL,DE).
  O sea NO es un helper de mapa: es el chequeo de borde de segmento.
- **El mapa NO está comprimido**: son **tile rows CRUDAS en ROM (32 de
  ancho), en SEGMENTOS**. La tabla 0xE2AC (RAM, armada al iniciar el nivel)
  lista los punteros a segmentos: {0xA444, 0xA4A4, 0xA564, 0xA624, 0xA63C}.
  El fill (0x99F6) lee del segmento actual (índice IX[23]&7) y avanza al
  siguiente al llegar al borde (DCOMPR).
- Punteros del scroll: 0xE71A=dest buffer (0xEA40), 0xE715=pos en buffer.

- **BLIT (sub_9A80) PORTADO Y VALIDADO ✅ (2026-06-18)** — `z_blit_playfield`
  en gfx.c: `name_table[fila] = buffer[(start+fila) mod 24]` (24 cols),
  donde start = (0xE715-0xE800)/24 = la posición de scroll en el buffer
  circular de 24 filas. Validado **24/24 filas byte-exacto** contra un frame
  real de openMSX (tests/fixtures/blit_buf.bin + blit_nt.bin, suite 3/3).
  Hallazgo: el texto "ROUND 1" del intro de nivel es un overlay aparte
  (copia literal, como los títulos), no parte del blit.

- **FORMATO DEL MAPA decodificado (2026-06-18)**: el mapa son **runs con
  PREFIJO DE LONGITUD** en ROM (no tiles planos): rutina 0x9A30 lee
  `[count][count tiles]` del staging (0xEA40) y los expande al buffer
  visible vía LDIR; `count==0` termina la fila, `count>=0xFE` = COMANDO
  (handler 0x95A8, sin explorar — probable repeat/columna). Por eso el
  buffer (0x24-27, tiles) no coincide byte a byte con el ROM (0x17=run de
  23): 0x17 era el contador, no un tile. El mapa está en segmentos (tabla
  0xE2AC: A444/A4A4/A564/...), filas de 24 efectivas, sección de apertura
  loopea 8 filas.

PORTADO Y VALIDADO (2026-06-18) — núcleo de generación de filas del scroll:
- **z_map_fetch** (sub 0x99D2-0x99F5): el mapa sale de `ROM[E2AC[(IX23&7)] +
  col]`, copia `(0x20-col)` bytes del mapa crudo al staging (0xEA40). Validado
  **32/32** vs openMSX (cap_segfetch.tcl). Confirma: staging = mapa CRUDO
  (0x17=run de 23), buffer visible = runs YA expandidos. Tabla 0xE2AC en la
  apertura: [0]=0,[1]=A444,[2]=A4A4,[3]=A564,[4]=A624,[5]=A63C.
- **z_map_expand** (sub 0x99FD-0x9A67): expansor de runs. 8 columnas en 0xE2E0
  (4B c/u: tilebase+0 [bit6=run multi-fila, 0x80=terminada], contador+1,
  ptr-programa ROM +2/+3). Cada columna copia runs `[destOffset,count,tiles]`
  al staging; al final LDIR de 24 bytes 0xEA48→(0xE715). Validado **byte-exacto
  contra el estado RAM completo** (0xE000-0xEBFF) antes/después de un pase real
  (cap_expander.tcl). Camino normal + especial(bit6) exactos.
- **z_blit_playfield** (sub 0x9A80): buffer 0xE800 → name table. Validado 24/24.

- **z_map_rebuild** (sub 0x9888-0x9A67): REBUILD completo de una fila. Prólogo
  (arma E2AE/E2B0/E2B2 desde 0xE702 + resetea IX/E71A) + driver loop (4
  entradas del bloque 0xE2C0, 8B c/u: pos+0/+1, ptr+2/+3, ptr2+4/+5, timer+6,
  timer2+7; stream de comandos 0xFF en 0x990D; segmento por `(IY+1)>>3&0x0E`;
  suma tile-base 0x17/0x2E según bits de IY+1) + fetch + expansor. Validado
  **byte-exacto contra el estado RAM completo** (cap_tick.tcl, complex_fired=0).
  Transcripción primero en Python (tools/sim_tick.py, 0 diffs) y luego en C.
  Llamado desde 0x9802 (que además hace SET 0,1 (IX+0) = flag dirty).

- **z_map_command** (sub 0x95A8 + 0x95C0 + 0x95ED + 0x9B22): COMMAND HANDLER
  del stream del mapa. Programa N columnas del bloque E2E0 (selector con bit3 +
  tile-base + ptr) y dispara **spawns de objetos** en la tabla 0xE620
  (slot-finder 0x9B22, escribe 0xE780/E150-E152/IX+29). Validado **byte-exacto
  vs RAM completa** de un call que dispara spawn (cap_cmd.tcl). Transcripción en
  Python (sim_cmd.py, 0 diffs) y luego C.

ARQUITECTURA DEL VM DE NIVEL COMPLETAMENTE MAPEADA (2026-06-18) — lo que falta
es portar/cablear esto (todo el motor de bajo nivel de arriba YA está validado):
- **Script VM**: IX+4/5 → script en ROM (nivel 1: ~0xA75B). Fetch 0x97D5 lee
  `[trigger:word][cont:word]` (→ E706/E704) y JP 0x94D1.
- **Dispatcher 0x94D1**: compara pos de scroll (0xE702) con el trigger (0xE706);
  si != → **avanza scroll 0x97E3**; si == → ejecuta el opcode: A=(E704)&0x0F,
  CALL 0x5C2E (salto por TABLA inline en 0x94EB) a un handler.
- **Handlers** (cada uno JP 0x97D5 al terminar): 0x9505/0x9508 y 0x956E arman
  entradas del bloque E2C0 (pos/ptr/timers=1); 0x95A2 → z_map_command (columnas
  E2E0 + spawn). 0x5C2E = primitiva de salto por tabla (pendiente de leer).
- **Avance de scroll 0x97E3-0x980D**: C=(IX+20); E715 -= 24 (una fila), envuelve
  a 0xEA28/C=0x17 en 0; (IX+20)=C; CALL 0x9888 (rebuild) — el paso de scroll por
  fila (8px). Scroll fino sub-tile: por el blit per-frame.
- **Blit per-frame 0x9A88-0x9AE2**: SETWRT (0x0053) + 24 OUTs/fila desde (E715)
  a name table 0x3800; tabla de split por fila IY=0xE180; camino de wrap 0x9AC5;
  IX+14/+20. z_blit_playfield ya validó la copia básica (24/24).
- **Init de nivel**: 0x9415 llena E2C0/E2E0 con 0x80; setea IX (IX+4/5=script
  ptr, IX+1C, etc.), E2AC[4/5]=A624/A63C, E702=0.
- Spawn de objetos (0xE620) ya cubierto por z_map_command (acopla con enemigos).
DETALLES CONCRETOS DEL VM (2026-06-18, para portar la próxima sesión):
- **Entry per-frame / level-init**: main loop 0x4272 → CALL 0x9405 (init:
  llena E2C0/E2E0 con 0x80 vía 0x9410; HL=script ptr → E704; primer trigger →
  E706; E702=trigger-1; RES 0(IX+0)) → CALL 0x946E (corre 0x94C3 ×24 = llena el
  buffer con las 24 filas iniciales). Script del NIVEL 1: **HL=0xA751**.
- **Driver de scroll fino 0x94A0-0x94D0**: acumula IX+16/+17 (subpíxel); al
  desbordar INC E702 y cae en 0x94D1. 0x94C3 = paso de fila (BIT3(IX+0)→CALL
  0x9AE4 blit; INC E702; → 0x94D1).
- **Dispatcher 0x94D1**: si E702!=E706 → JP 0x97E3 (avanza buffer 1 fila +
  rebuild 0x9888 + RET). Si == → A=(E704)&0x0F; CALL 0x5C2E (salto por tabla).
- **0x5C2E** = primitiva "JP tabla_inline[A]" (EX(SP),HL; A*2; indexa; RET).
- **Tabla de handlers @ 0x94EB** (opcode = byte&0x0F). Disasm leído de cada uno
  (lo que toca + bytes de operando que consume del script; todos terminan en
  JP 0x97D5 salvo nota):
  - [0]0x97A8 SONIDO/control: (E12D)=byte; si bit2 cae en [1]. ~1 byte.
  - [1]0x97B3 SPAWN objetos: B=cnt; B× spawn en 0xE620 (0x97BC, slot 0x9B22,
    escribe 0x45+3B). 1+3*B bytes.
  - [2]0x9505 MAPA: B=cnt; B×[selector+pos+IY1+ptr2] arma entradas E2C0
    (timers=1). 1+5*B bytes.
  - [3]0x9537 MAPA: B=cnt; mueve/copia entradas E2 (LDI×7) entre slots. var.
  - [4]0x956C MAPA: como [2] pero (IY+0)+=pos (suma). 1+5*B bytes.
  - [5]0x95A0 MAPA: C=0; CALL z_map_command (programa columnas E2E0 + spawn).
  - [6]0x9678 MAPA: (E71C)=byte [= índice de segmento, alimenta el fetch]. 1B.
  - [7]0x9680 MAPA: B=cnt; B× marca entrada E2C0 = 0x80 (libera). 1+B bytes.
  - [8]0x9699 SPRITE/SCORE: (E720)=word; setup E180/E102/E15E; render score
    (0x5BFC/0x42F8). 2 bytes (+efectos VRAM/sprite, no buffer).
  - [9]0x96DE SALTO de sección: HL=word; JP 0x9433 (re-init con nuevo script +
    CALL 0x4C68). 2 bytes. NO vuelve por 0x97D5 (redirige).
  - [10]0x96E5 VRAM: (IX+35)=byte; carga patrones a VRAM (0x970A/0x0053). 1B.
  - [11]0x9742 MAPA+param: LDIR 4B→E155; tabla 0x976C→E153; CALL 0x95C0 (arma
    columna 0 de E2E0). 4 bytes (+lo que lee 0x95C0).
  - [12]0x977D DIFICULTAD/sonido: acumula en E132/E12E/E12D. 1 byte.
  Handlers de MAPA (afectan buffer): 2,3,4,5,6,7,11. El resto consume operandos
  pero sus efectos (E1xx/sprite/VRAM/score) NO tocan el buffer 0xE800 — al
  validar el fill comparar SOLO 0xE800-0xEA3F + bloques E2C0/E2E0.
- **0x97D5** = fetch: lee [trigger:word] siguiente → E706, E704=ptr; JP 0x94D1.
- Oráculo de validación guardado: tests/fixtures/lf_before.bin (RAM en 0x9405)
  + lf_after.bin (RAM tras 0x946E, buffer lleno). Portar init+VM+handlers, correr
  24 pasos, y validar el buffer 0xE800 byte-exacto. Faltan disasm de varios
  handlers (0x9678/0x9699/0x96DE/0x96E5/0x9742/0x977D).
FASE 2 COMPLETA Y EN VIVO (2026-06-18): el VM está PORTADO (z_level_init +
z_vm_step + 12 handlers + rebuild + command) y VALIDADO byte-exacto (init + 24
pasos = buffer del nivel 1, 0/576, SIN datos de captura). main.c: título →
ESPACIO → el nivel 1 SCROLLEA en vivo. Confirmado fiel: la apertura usa solo
tiles 0x24-0x27, los 4 idénticos (patrón+color) título-vs-gameplay. El scroll
corre ~2976 pasos (≈5 min) antes de toparse con el handler 9 (salto de sección,
no portado). z_decompress NO se usa para el mapa.
Pendientes de Fase 2 (no urgentes): handler 9 (0x96DE→0x9433, +0x9444/0x4C68);
blit per-frame real 0x9A88 (uso z_blit_playfield, validado 24/24); HUD/score.

### Fase 3 — Jugador (nave): movimiento + disparo  ← PRÓXIMA
Input, límites, sprite, disparo principal y la rotación de armas
secundarias (Zanac tiene 8 armas). Validar posición/sprites frame a frame.
ENTRY POINTS hallados (2026-06-18): SAT en VRAM **0x3B80** (reg5 VDP=0x77).
La NAVE = sprites 0+1 del SAT, patrones **0x38/0x3C** (16x16, 2 colores),
posición de gameplay ~X=0x78 Y=0x8F (centro-abajo), colores 0x8F/0x81. Los
patrones de sprite ya están en VRAM 0x1800 (idénticos título/gameplay). El
juego NO usa BIOS GTSTCK/GTTRIG — lee el joystick por el puerto PSG (reg 14/15).
Falta: hallar las variables de posición del jugador en RAM, la rutina de
movimiento/límites y el refresh del SAT (per-frame, ~0x9AE4). El HAL ya ofrece
hal_joystick_read()/hal_key_pressed() para alimentar la lógica porteada.

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
