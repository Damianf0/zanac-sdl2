#!/usr/bin/env python3
"""Suite de tests del port de Zanac (compara el port contra oráculos openMSX).

Uso:  python tests/run_tests.py            (compila con build.ps1 y testea)
      python tests/run_tests.py --no-build (usa zanac.exe ya compilado)
"""
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX  = os.path.join(ROOT, 'tests', 'fixtures')
EXE  = os.path.join(ROOT, 'zanac.exe')


def check(name, fn):
    try:
        errs = fn()
    except Exception as e:
        errs = ['EXCEPCION: %r' % e]
    print(('[PASS] ' if not errs else '[FAIL] ') + name)
    for e in errs:
        print('       ' + e)
    return not errs


def main():
    if '--no-build' not in sys.argv:
        r = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass',
                            '-File', os.path.join(ROOT, 'build.ps1')],
                           cwd=ROOT, capture_output=True, text=True)
        ok = 'OK ->' in r.stdout
        print(('[PASS] ' if ok else '[FAIL] ') + 'build')
        if not ok:
            print(r.stdout[-800:], r.stderr[-800:]); return
    if not os.path.exists(EXE):
        print('[FAIL] no existe', EXE); return

    results = []

    # --- descompresor de gráficos (sub_5CDC) vs openMSX ----------------------
    # El port corre las 13 invocaciones del título y produce el stream de
    # salida del descompresor (17264 bytes); debe ser idéntico a los primeros
    # 17264 bytes del stream de escrituras VDP capturado de openMSX
    # (tools/trace_out.tcl). El resto del stream son copias literales (otra
    # ruta, aún sin portar).
    def t_decomp():
        out = os.path.join(tempfile.gettempdir(), 'zdecomp.txt')
        env = dict(os.environ, ZANAC_DECOMP=out)
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        mine = open(out).read().split()
        os.remove(out)
        ref = open(os.path.join(FIX, 'decomp_title.txt')).read().split()
        if len(mine) != 17264:
            return ['el port produjo %d bytes (se esperaban 17264)' % len(mine)]
        bad = sum(1 for i in range(len(mine)) if mine[i] != ref[i])
        if bad:
            first = next(i for i in range(len(mine)) if mine[i] != ref[i])
            return ['%d/%d bytes difieren (primero f%d: port %s vs openMSX %s)'
                    % (bad, len(mine), first, mine[first], ref[first])]
        return []
    results.append(check('descompresor de gráficos (sub_5CDC, 17264 bytes vs openMSX)',
                         t_decomp))

    # --- gráficos del título (patrones+sprites+color) vs VRAM de openMSX ------
    # ZANAC_TITLEGFX corre el cargador (descompresor por la receta de SETWRT)
    # y vuelca VRAM 0x0000-0x37FF; debe ser idéntico a la VRAM real del título
    # (tools/cap_vram.tcl → vram_title.bin) en patrones, sprites y color.
    # (La name table 0x3800+ = copias literales, próximo incremento.)
    def t_titlegfx():
        out = os.path.join(tempfile.gettempdir(), 'ztitlegfx.bin')
        env = dict(os.environ, ZANAC_TITLEGFX=out)
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'vram_title.bin'), 'rb').read()
        errs = []
        for name, s, e in (('pattern', 0, 0x1800), ('sprite', 0x1800, 0x2000),
                           ('color', 0x2000, 0x3800), ('name table', 0x3800, 0x3B00)):
            bad = sum(1 for i in range(s, e) if got[i] != ref[i])
            if bad:
                errs.append('%s: %d/%d bytes difieren' % (name, bad, e - s))
        return errs
    results.append(check('título completo (patrones+sprites+color+name table vs openMSX)',
                         t_titlegfx))

    # --- blit del scroll (sub_9A80): buffer del mapa → name table vs openMSX -
    # ZANAC_BLIT corre z_blit_playfield sobre un buffer real capturado de
    # openMSX (blit_buf.bin) con la posición de scroll real (blit_start) y
    # debe reproducir el playfield (24×24) de la name table (blit_nt.bin).
    def t_blit():
        out = os.path.join(tempfile.gettempdir(), 'zblit.bin')
        start = open(os.path.join(FIX, 'blit_start.txt')).read().strip()
        env = dict(os.environ, ZANAC_BLIT=out,
                   ZANAC_BLITBUF=os.path.join(FIX, 'blit_buf.bin'),
                   ZANAC_BLITSTART=start)
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'blit_nt.bin'), 'rb').read()
        bad = sum(1 for row in range(24) for col in range(24)
                  if got[row*32+col] != ref[row*32+col])
        return [] if not bad else ['%d/576 celdas del playfield difieren' % bad]
    results.append(check('blit del scroll (sub_9A80, playfield vs openMSX)',
                         t_blit))

    # --- fetch de fila de mapa (sub 0x99D2-0x99F5) vs staging de openMSX ------
    # ZANAC_MAPFETCH corre z_map_fetch con la tabla de segmentos 0xE2AC y los
    # IX+23/IX+25 reales (tests/fixtures/mapfetch.txt) y debe reproducir los
    # 32 bytes de mapa crudo que el juego copió al staging (0xEA40). Confirma
    # que el mapa sale de E2AC[(ix23&7)]+col, no de 0xA564 crudo.
    def t_mapfetch():
        fx = {}
        for line in open(os.path.join(FIX, 'mapfetch.txt')):
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            fx[k] = v
        ref = [int(x, 16) for x in fx['staging'].split(',')]
        out = os.path.join(tempfile.gettempdir(), 'zmapfetch.bin')
        env = dict(os.environ, ZANAC_MAPFETCH=out, ZANAC_MF_TBL=fx['tbl'],
                   ZANAC_MF_IX23=fx['ix23'], ZANAC_MF_IX25=fx['ix25'])
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        bad = sum(1 for i in range(32) if got[i] != ref[i])
        return [] if not bad else ['%d/32 bytes del staging difieren' % bad]
    results.append(check('fetch de fila de mapa (sub 0x99D2, staging vs openMSX)',
                         t_mapfetch))

    # --- expansor de runs del scroll (sub 0x99FD-0x9A67) vs RAM de openMSX ----
    # ZANAC_MAPEXPAND carga el estado RAM (0xE000-0xEBFF) capturado JUSTO antes
    # de un pase del expansor (exp_before.bin), corre z_map_expand y debe
    # reproducir EXACTAMENTE la RAM resultante (exp_after.bin): las 8 columnas
    # expandidas + la copia de 24 bytes al buffer visible. Pase sin comando
    # 0xFE ni terminador 0x00 (cmd_fired=0 en la captura).
    def t_mapexpand():
        out = os.path.join(tempfile.gettempdir(), 'zexpand.bin')
        env = dict(os.environ, ZANAC_MAPEXPAND=out,
                   ZANAC_ME_IN=os.path.join(FIX, 'exp_before.bin'))
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'exp_after.bin'), 'rb').read()
        bad = [i for i in range(len(ref)) if got[i] != ref[i]]
        if bad:
            return ['%d/%d bytes de RAM difieren (primero 0x%04X)'
                    % (len(bad), len(ref), 0xE000 + bad[0])]
        return []
    results.append(check('expansor de runs del scroll (sub 0x99FD, RAM vs openMSX)',
                         t_mapexpand))

    # --- rebuild completo del scroll (sub 0x9888-0x9A67) vs RAM de openMSX ----
    # ZANAC_MAPREBUILD carga la RAM (0xE000-0xEBFF) capturada en la entrada de
    # 0x9888 (tick_before.bin) y debe reproducir EXACTAMENTE la RAM al RET
    # (tick_after.bin): prólogo + driver loop (bloque E2C0) + fetch + expansor.
    # Tick sin comando 0x95A8 / recarga 0x95ED / spawn 0x9B22 (complex_fired=0).
    def t_maprebuild():
        out = os.path.join(tempfile.gettempdir(), 'zrebuild.bin')
        env = dict(os.environ, ZANAC_MAPREBUILD=out,
                   ZANAC_MR_IN=os.path.join(FIX, 'tick_before.bin'))
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'tick_after.bin'), 'rb').read()
        bad = [i for i in range(len(ref)) if got[i] != ref[i]]
        if bad:
            return ['%d/%d bytes de RAM difieren (primero 0x%04X)'
                    % (len(bad), len(ref), 0xE000 + bad[0])]
        return []
    results.append(check('rebuild completo del scroll (sub 0x9888, RAM vs openMSX)',
                         t_maprebuild))

    # --- command handler + spawn del mapa (sub 0x95A8) vs RAM de openMSX ------
    # ZANAC_MAPCMD carga la RAM capturada en la entrada de 0x95A8 (cmd_before)
    # con HL/C reales y debe reproducir EXACTAMENTE la RAM al RET: las columnas
    # programadas en E2E0 + los objetos spawneados en la tabla 0xE620 (este
    # caso SI dispara el spawn 0x9B22). Es la compuerta de generación del mapa.
    def t_mapcmd():
        meta = {}
        for line in open(os.path.join(FIX, 'cmd_meta.txt')):
            if '=' in line:
                k, v = line.strip().split('=', 1); meta[k] = v
        out = os.path.join(tempfile.gettempdir(), 'zmapcmd.bin')
        env = dict(os.environ, ZANAC_MAPCMD=out,
                   ZANAC_MC_IN=os.path.join(FIX, 'cmd_before.bin'),
                   ZANAC_MC_HL=meta['HL'], ZANAC_MC_C=meta['C'])
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'cmd_after.bin'), 'rb').read()
        bad = [i for i in range(len(ref)) if got[i] != ref[i]]
        if bad:
            return ['%d/%d bytes de RAM difieren (primero 0x%04X)'
                    % (len(bad), len(ref), 0xE000 + bad[0])]
        return []
    results.append(check('command handler + spawn del mapa (sub 0x95A8, RAM vs openMSX)',
                         t_mapcmd))

    # --- VM de nivel: fill inicial del playfield (0x9405+0x946E) vs openMSX ---
    # ZANAC_LEVELFILL corre z_level_init (nivel 1) desde RAM en cero y debe
    # reproducir el buffer del mapa (0xE800-0xEA3F) + bloques de control
    # (E2C0-E2FF) capturados tras el fill de 24 filas (lf_after.bin). Valida
    # el VM completo (init + dispatcher + 13 handlers + fetch + rebuild) SIN
    # usar datos de captura como semilla (solo 2 constantes de arranque).
    def t_levelfill():
        out = os.path.join(tempfile.gettempdir(), 'zlevelfill.bin')
        env = dict(os.environ, ZANAC_LEVELFILL=out)
        r = subprocess.run([EXE], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(out):
            return ['exe falló']
        got = open(out, 'rb').read()
        os.remove(out)
        ref = open(os.path.join(FIX, 'lf_after.bin'), 'rb').read()
        errs = []
        for name, s, e in (('buffer 0xE800', 0xE800, 0xEA40),
                           ('bloques E2C0', 0xE2C0, 0xE300)):
            bad = sum(1 for i in range(s - 0xE000, e - 0xE000) if got[i] != ref[i])
            if bad:
                errs.append('%s: %d/%d bytes difieren' % (name, bad, e - s))
        return errs
    results.append(check('VM de nivel: fill del playfield (0x9405+VM, buffer vs openMSX)',
                         t_levelfill))

    ok = sum(results)
    print('\n%d/%d suites OK' % (ok, len(results)))


if __name__ == '__main__':
    main()
