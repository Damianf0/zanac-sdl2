# build.ps1 — Compila The Castle a .exe nativo de Windows (MinGW-w64 + SDL2).
# Uso:  powershell -ExecutionPolicy Bypass -File .\build.ps1
$ErrorActionPreference = 'Stop'
$gcc = "C:\Users\Soporte\Desktop\_buildtools\mingw\mingw64\bin\gcc.exe"
$sdl = "C:\Users\Soporte\Desktop\_buildtools\sdl2\SDL2-2.32.10\x86_64-w64-mingw32"
$src = $PSScriptRoot

$cfiles = (Get-ChildItem "$src\*.c").Name
Write-Host "Compilando $($cfiles.Count) archivos..." -ForegroundColor Cyan
Push-Location $src
& $gcc -O2 -DSDL_MAIN_HANDLED -std=c99 -static-libgcc `
    -Wno-unused-parameter -Wno-unused-function `
    $cfiles `
    "-I$sdl\include" "-I$sdl\include\SDL2" `
    "-L$sdl\lib" -lmingw32 -lSDL2main -lSDL2 -lm `
    -o "$src\zanac.exe"
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Write-Host "FALLO (exit $code)" -ForegroundColor Red; exit $code }

# Asegurar runtime junto al exe
if (-not (Test-Path "$src\SDL2.dll")) { Copy-Item "$sdl\bin\SDL2.dll" "$src\SDL2.dll" }
Write-Host "OK -> $src\zanac.exe ($([math]::Round((Get-Item "$src\zanac.exe").Length/1KB,0)) KB)" -ForegroundColor Green
Write-Host "Correr: .\zanac.exe" -ForegroundColor Green
