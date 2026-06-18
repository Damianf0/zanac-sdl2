# En un frame de gameplay vuelca: buffer del mapa (0xE800-EA3F, 24x24=576B),
# name table playfield (0x3800-3AFF), E715 (pos scroll) y el puntero fuente
# del mapa (0xE71C..? lo buscamos: dump de 0xE710-0xE720). -> archivos .bin/.txt
proc snap {} {
    set b [open "ss_buf.bin" wb]; fconfigure $b -translation binary
    for {set a 0xE800} {$a < 0xEA40} {incr a} { puts -nonewline $b [binary format c [debug read memory $a]] }
    close $b
    set n [open "ss_nt.bin" wb]; fconfigure $n -translation binary
    for {set a 0x3800} {$a < 0x3B00} {incr a} { puts -nonewline $n [binary format c [debug read VRAM $a]] }
    close $n
    set d [open "ss_state.txt" w]
    puts $d "E715=[format %02X%02X [debug read memory 0xE716] [debug read memory 0xE715]]"
    set p {}
    for {set a 0xE710} {$a < 0xE722} {incr a} { lappend p [format %02X [debug read memory $a]] }
    puts $d "E710..E721: [join $p ,]"
    close $d
    exit
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 18  { snap }
