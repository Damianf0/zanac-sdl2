# Captura la VRAM completa (16 KB) del título de Zanac (estable a los 6s) y
# los 8 registros VDP. Salida: tests/fixtures/vram_title.bin (binario) +
# tests/fixtures/vdp_title.txt (registros). Objetivo byte-exacto del port.
after time 6 {
    set data [debug read_block VRAM 0 0x4000]
    set f [open "tests/fixtures/vram_title.bin" wb]
    fconfigure $f -translation binary
    puts -nonewline $f $data
    close $f
    set g [open "tests/fixtures/vdp_title.txt" w]
    for {set r 0} {$r < 8} {incr r} {
        puts $g [format "R%d=%02X" $r [debug read "VDP regs" $r]]
    }
    close $g
    exit
}
