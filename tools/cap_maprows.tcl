# Captura las filas del mapa que entran al buffer (fill 0x99F6 -> staging
# 0xEA40). Cada vez que se escribe 0xEA40 (nueva fila), vuelca los 32 bytes
# 0xEA40-EA5F + el HL fuente. Primeras 24 filas. -> cap_maprows_out.txt
set ::log {}
set ::on 0
debug set_watchpoint write_mem 0xEA40 {} {
    if {$::on && [llength $::log] < 24} {
        set row {}
        for {set i 0} {$i < 32} {incr i} { lappend row [format %02X [debug read memory [expr {0xEA40+$i}]]] }
        lappend ::log [format "HL=%04X: %s" [reg HL] [join $row " "]]
    }
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::on 1 }
after time 22  {
    set f [open "cap_maprows_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
