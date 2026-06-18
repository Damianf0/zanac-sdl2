# Captura de referencia: arranca Zanac, espera a que llegue al título/juego
# y guarda un screenshot + un volcado del modo de pantalla y registros VDP.
after time 8 {
    screenshot -raw zanac_ref.png
    set f [open "zanac_ref_vdp.txt" w]
    puts $f "screen mode regs:"
    for {set r 0} {$r < 8} {incr r} {
        puts $f "  R$r = [format %02X [debug read {VDP regs} $r]]"
    }
    close $f
    exit
}
