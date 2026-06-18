# Captura el PATRON de escritura a la name table durante el gameplay:
# (addr, val) de las primeras 160 escrituras tras t=11, rastreando el latch
# del puerto 0x99. Revela si reescribe filas contiguas / toda la tabla / etc.
# Salida -> probe_scroll3_out.txt
set ::latch {}
set ::addr 0
set ::log {}
set ::on 0
debug set_watchpoint write_io 0x99 {} {
    lappend ::latch $::wp_last_value
    if {[llength $::latch] >= 2} {
        set ::addr [expr {[lindex $::latch 0] | (([lindex $::latch 1] & 0x3F) << 8)}]
        set ::latch {}
    }
}
debug set_watchpoint write_io 0x98 {} {
    if {$::on && $::addr >= 0x3800 && $::addr < 0x3B00 && [llength $::log] < 160} {
        lappend ::log [format "%04X=%02X" $::addr $::wp_last_value]
    }
    set ::addr [expr {($::addr + 1) & 0x3FFF}]
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::on 1 }
after time 16  {
    set f [open "probe_scroll3_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
