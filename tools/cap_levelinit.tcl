# Encuentra la INIT del nivel: watchpoint de escritura sobre el bloque de
# control E2C0 (0xE2C0-0xE2FF) y E702; loguea (addr, val, PC, HL fuente) de
# las primeras escrituras al entrar al gameplay. Tambien vuelca el estado
# completo de los bloques al primer 0x9888.  -> levelinit_out.txt
set ::armed 0
set ::log {}
set ::snapped 0
debug set_watchpoint write_mem {0xE2C0 0xE2FF} {$::armed} {
    if {[llength $::log] < 40} {
        lappend ::log [format "%s=%02X PC=%04X HL=%04X DE=%04X" \
            $::wp_last_address $::wp_last_value [reg PC] [reg HL] [reg DE]]
    }
}
debug set_bp 0x9888 {$::armed} {
    if {!$::snapped} {
        set ::snapped 1
        set s {}
        lappend s "--- snapshot bloques de control al 1er 0x9888 ---"
        lappend s "E702=[format %02X [debug read memory 0xE702]]"
        set t {}
        for {set i 0} {$i < 16} {incr i} { lappend t [format %02X [debug read memory [expr {0xE2AC+$i}]]] }
        lappend s "E2AC(16): [join $t ,]"
        set t {}
        for {set i 0} {$i < 32} {incr i} { lappend t [format %02X [debug read memory [expr {0xE2C0+$i}]]] }
        lappend s "E2C0(32): [join $t ,]"
        set t {}
        for {set i 0} {$i < 32} {incr i} { lappend t [format %02X [debug read memory [expr {0xE2E0+$i}]]] }
        lappend s "E2E0(32): [join $t ,]"
        set t {}
        for {set i 0} {$i < 32} {incr i} { lappend t [format %02X [debug read memory [expr {0xE700+$i}]]] }
        lappend s "E700-IX(32): [join $t ,]"
        set ::snap $s
    }
}
after time 8    { keymatrixdown 8 1 }
after time 8.2  { keymatrixup 8 1 }
after time 9    { keymatrixdown 8 1 }
after time 9.2  { keymatrixup 8 1 }
after time 8.5  { set ::armed 1 }
after time 14   {
    set f [open "levelinit_out.txt" w]
    puts $f "--- escrituras a E2C0 (addr=val PC HL DE) ---"
    puts $f [join $::log "\n"]
    if {[info exists ::snap]} { puts $f [join $::snap "\n"] }
    close $f
    exit
}
