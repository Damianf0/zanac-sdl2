# Entra al juego (SPACE a los 8s) y mide DONDE escribe el VDP durante el
# gameplay: cuenta escrituras por region (rastreando el latch de direccion
# del puerto 0x99) en una ventana de 2s. Revela el mecanismo de scroll:
#   pattern 0x0000-17FF / sprite-pat 0x1800-1FFF / color 0x2000-37FF /
#   name 0x3800-3AFF / sprite-attr 0x3B00+.
# Salida -> probe_scroll_out.txt
set ::latch {}
set ::addr 0
array set ::reg {pat 0 spr 0 col 0 name 0 sat 0 otro 0}
set ::on 0
debug set_watchpoint write_io 0x99 {} {
    lappend ::latch $::wp_last_value
    if {[llength $::latch] >= 2} {
        set ::addr [expr {[lindex $::latch 0] | (([lindex $::latch 1] & 0x3F) << 8)}]
        set ::latch {}
    }
}
debug set_watchpoint write_io 0x98 {} {
    if {$::on} {
        set a $::addr
        if {$a < 0x1800} { incr ::reg(pat) } \
        elseif {$a < 0x2000} { incr ::reg(spr) } \
        elseif {$a < 0x3800} { incr ::reg(col) } \
        elseif {$a < 0x3B00} { incr ::reg(name) } \
        elseif {$a < 0x3C00} { incr ::reg(sat) } \
        else { incr ::reg(otro) }
    }
    set ::addr [expr {($::addr + 1) & 0x3FFF}]
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::on 1 }
after time 13  {
    set ::on 0
    set f [open "probe_scroll_out.txt" w]
    puts $f "escrituras VDP en 2s de gameplay (t=11..13):"
    foreach k {pat spr col name sat otro} { puts $f "  $k = $::reg($k)" }
    close $f
    exit
}
