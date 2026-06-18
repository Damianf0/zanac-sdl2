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

    ok = sum(results)
    print('\n%d/%d suites OK' % (ok, len(results)))


if __name__ == '__main__':
    main()
