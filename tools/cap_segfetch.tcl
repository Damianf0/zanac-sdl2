# Captura el FETCH de fila de mapa (0x99D2-0x99F5): en la entrada (0x99D2)
# graba IX+23, IX+25, puntero E71A y la tabla de segmentos 0xE2AC[8]; tras el
# LDIR (0x99F7) vuelca el staging escrito. Valida que el mapa sale de
# E2AC[(IX+23)&7]+col, NO de 0xA564 crudo.  -> cap_segfetch_out.txt
set ::armed 0
set ::got 0
array set ::in {}

proc rd16 {a} { return [expr {[debug read memory $a] | ([debug read memory [expr {$a+1}]]<<8)}] }

debug set_bp 0x99D2 {} {
    if {$::armed && !$::got} {
        set ix [reg IX]
        set ::in(ix)   $ix
        set ::in(ix23) [debug read memory [expr {($ix+23)&0xFFFF}]]
        set ::in(ix25) [debug read memory [expr {($ix+25)&0xFFFF}]]
        set ::in(e71a) [rd16 0xE71A]
        set t {}
        for {set i 0} {$i < 16} {incr i} { lappend t [format %02X [debug read memory [expr {0xE2AC+$i}]]] }
        set ::in(tbl) $t
    }
}

debug set_bp 0x99F7 {} {
    if {$::armed && !$::got && [info exists ::in(e71a)]} {
        set ::got 1
        set st {}
        for {set i 0} {$i < 32} {incr i} { lappend st [format %02X [debug read memory [expr {$::in(e71a)+$i}]]] }
        set f [open "cap_segfetch_out.txt" w]
        puts $f "IX=[format %04X $::in(ix)] IX23=[format %02X $::in(ix23)] IX25=[format %02X $::in(ix25)] E71A=[format %04X $::in(e71a)]"
        puts $f "E2AC_tbl: [join $::in(tbl) ,]"
        puts $f "staging_post(32B desde E71A): [join $st ,]"
        close $f
        exit
    }
}

after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::armed 1 }
after time 20  { exit }
