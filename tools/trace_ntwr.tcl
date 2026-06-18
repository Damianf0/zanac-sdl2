# Reconstruye la direccion de escritura del VDP (latch del puerto 0x99: 2
# bytes -> addr = lo | (hi&0x3F)<<8) y, en cada dato (puerto 0x98) con addr
# en la name table (0x3800-0x3AFF), loguea (addr, val, PC). Asi se ve QUE
# escribe el logo/score y desde donde. Primeras 120 ops. -> trace_ntwr_out.txt
set ::latch {}
set ::addr 0
set ::log {}
debug set_watchpoint write_io 0x99 {} {
    lappend ::latch $::wp_last_value
    if {[llength $::latch] >= 2} {
        set lo [lindex $::latch 0]; set hi [lindex $::latch 1]
        set ::addr [expr {$lo | (($hi & 0x3F) << 8)}]
        set ::latch {}
    }
}
debug set_watchpoint write_io 0x98 {} {
    if {$::addr >= 0x3800 && $::addr < 0x3B00 && [reg PC] != 0x23CA && [llength $::log] < 200} {
        lappend ::log [format "%04X val=%02X pc=%04X" $::addr $::wp_last_value [reg PC]]
    }
    set ::addr [expr {($::addr + 1) & 0x3FFF}]
}
after time 6.5 {
    set f [open "trace_ntwr_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
