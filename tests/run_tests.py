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
        ref = open(os.path.join(FIX, 'vram_title.bin'), 'rb').read()[:0x3800]
        errs = []
        for name, s, e in (('pattern', 0, 0x1800), ('sprite', 0x1800, 0x2000),
                           ('color', 0x2000, 0x3800)):
            bad = sum(1 for i in range(s, e) if got[i] != ref[i])
            if bad:
                errs.append('%s: %d/%d bytes difieren' % (name, bad, e - s))
        return errs
    results.append(check('gráficos del título (patrones+sprites+color vs openMSX)',
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

    ok = sum(results)
    print('\n%d/%d suites OK' % (ok, len(results)))


if __name__ == '__main__':
    main()
