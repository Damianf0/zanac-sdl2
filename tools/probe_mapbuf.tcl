# Verifica que 0xE800 sea el buffer del mapa: durante gameplay compara
# 0xE800.. (RAM) con la fila 0 del playfield en la name table 0x3800..
# y dumpea unas filas del buffer. -> probe_mapbuf_out.txt
proc snap {} {
    set out {}
    for {set r 0} {$r < 4} {incr r} {
        set ram {}; set vram {}
        for {set c 0} {$c < 24} {incr c} {
            lappend ram  [format %02X [debug read memory [expr {0xE800 + $r*24 + $c}]]]
            lappend vram [format %02X [debug read VRAM    [expr {0x3800 + $r*32 + $c}]]]
        }
        lappend out "fila $r RAM(E800): [join $ram ,]"
        lappend out "fila $r VRAM(3800): [join $vram ,]"
    }
    set f [open "probe_mapbuf_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 12  { snap }
