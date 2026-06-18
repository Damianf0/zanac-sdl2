# Vuelca un bloque de RAM durante gameplay (codigo residente en RAM).
# Rango: 0x11C0-0x1210 (el handler de RST 0x20 = 0x11C6). -> dump_ram_out.txt
proc snap {} {
    set out {}
    for {set a 0x11C0} {$a < 0x1210} {incr a 16} {
        set row {}
        for {set i 0} {$i < 16} {incr i} { lappend row [format %02X [debug read memory [expr {$a+$i}]]] }
        lappend out [format "%04X: %s" $a [join $row " "]]
    }
    set f [open "dump_ram_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 12  { snap }
