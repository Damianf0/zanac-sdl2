# Observa el scroll: entra al juego y en 8 frames consecutivos (interrupcion
# 0x0038) vuelca la columna 0 de la name table (24 filas: 0x3800+row*32) y un
# checksum de toda la name table. Asi se ve si las filas se desplazan (scroll
# por tiles) y en que direccion. -> probe_scroll2_out.txt
set ::log {}
set ::cap 0
set ::frames 0
proc snap {} {
    if {!$::cap} return
    set col {}
    for {set r 0} {$r < 24} {incr r} {
        lappend col [format %02X [debug read VRAM [expr {0x3800 + $r*32}]]]
    }
    set sum 0
    for {set i 0} {$i < 768} {incr i} { incr sum [debug read VRAM [expr {0x3800+$i}]] }
    lappend ::log "f$::frames col0=[join $col ,] sum=$sum"
    incr ::frames
    if {$::frames >= 8} {
        set f [open "probe_scroll2_out.txt" w]; puts $f [join $::log "\n"]; close $f
        exit
    }
}
debug set_bp 0x0038 {} { snap }
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::cap 1 }
after time 20  {
    set f [open "probe_scroll2_out.txt" w]; puts $f "TIMEOUT frames=$::frames"; close $f
    exit
}
