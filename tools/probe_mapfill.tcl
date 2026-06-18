# Ubica el MOTOR del mapa: watchpoint de escritura sobre el buffer 0xE800-EBFF
# durante gameplay. Histograma del PC que escribe + dump de las primeras 40
# (addr, val, HL, PC) para ver la fuente. -> probe_mapfill_out.txt
array set ::pc {}
set ::log {}
set ::on 0
debug set_watchpoint write_mem {0xE800 0xEBFF} {} {
    if {$::on} {
        incr ::pc([reg PC])
        if {[llength $::log] < 40} {
            lappend ::log [format "%s=%02X HL=%04X DE=%04X PC=%04X" \
                $::wp_last_address $::wp_last_value [reg HL] [reg DE] [reg PC]]
        }
    }
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::on 1 }
after time 13  {
    set ::on 0
    set out {"PC que escribe el buffer del mapa:"}
    foreach k [lsort -integer [array names ::pc]] { lappend out [format "  PC %04X x%d" $k $::pc($k)] }
    lappend out "--- primeras escrituras (addr=val HL DE PC):"
    foreach l $::log { lappend out "  $l" }
    set f [open "probe_mapfill_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
