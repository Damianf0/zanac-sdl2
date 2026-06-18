# Durante gameplay vuelca: el handler de RST 0x20 (0x0020-0x002F en RAM),
# la tabla de segmentos del mapa (0xE2AC-0xE2CF), y punteros relevantes
# (0xE71A, 0xE715, 0xE2AC). -> probe_rst20_out.txt
proc snap {} {
    set out {}
    set h {}
    for {set a 0x0020} {$a < 0x0030} {incr a} { lappend h [format %02X [debug read memory $a]] }
    lappend out "RST20 handler @0020: [join $h ,]"
    set t {}
    for {set a 0xE2AC} {$a < 0xE2D0} {incr a} { lappend t [format %02X [debug read memory $a]] }
    lappend out "tabla @E2AC: [join $t ,]"
    lappend out [format "ptr E71A=%02X%02X  E715=%02X%02X" \
        [debug read memory 0xE71B] [debug read memory 0xE71A] \
        [debug read memory 0xE716] [debug read memory 0xE715]]
    set f [open "probe_rst20_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 12  { snap }
