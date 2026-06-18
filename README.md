# Zanac (Compile / Pony Canyon, 1986) — Port fiel a Windows

Port nativo a Windows (C + SDL2) del shoot'em-up de MSX **Zanac**,
reconstruido **función por función desde el desensamblado de la ROM** y
validado contra el emulador **openMSX** como oráculo.

Hereda la metodología y la infraestructura del port fiel de **The Castle**
(que a su vez es heredado del trabajo inicial de **Víctor**).

> **Estado: Fase 0 (fundación) — en curso.** El motor todavía no está
> portado; ver `PLAN_PORT_FIEL.md` para el roadmap.

## Lo que ya está

- `zanac.rom` — ROM original (32 KB, cartucho MSX).
- `tools/z80dis.py` — desensamblador Z80 propio (descenso recursivo),
  **validado contra openMSX** (424/424 instrucciones).
- `zanac_disasm.asm` — desensamblado inicial (crece al portar).
- Confirmado: Zanac corre en **SCREEN 2 + sprites 16×16** (mismo modo de
  video que The Castle → el HAL se reusa).

## Herramientas

```
python tools/z80dis.py zanac.rom zanac_disasm.asm   # (re)generar el disasm
```

Los oráculos de openMSX viven en `tools/*.tcl` (se invocan vía
`openmsx.exe -carta zanac.rom -script tools/X.tcl`).

---

*Port fiel reconstruido desde el desensamblado, validado contra openMSX.
Hereda de The Castle (y del trabajo inicial de Víctor).*
