# Captura, en un frame de gameplay, el buffer del mapa (0xE800-0xEAFF, 768B)
# y la name table (0x3800-0x3AFF, 768B) para descubrir el mapeo del blit
# (offset de fila / ancho) y validar el port. + el contador de filas IX[20]
# si se puede. Salidas: blit_buf.bin, blit_nt.bin.
proc snap {} {
    set b [open "blit_buf.bin" wb]; fconfigure $b -translation binary
    for {set a 0xE800} {$a < 0xEB00} {incr a} { puts -nonewline $b [binary format c [debug read memory $a]] }
    close $b
    set n [open "blit_nt.bin" wb]; fconfigure $n -translation binary
    for {set a 0x3800} {$a < 0x3B00} {incr a} { puts -nonewline $n [binary format c [debug read VRAM $a]] }
    close $n
    set d [open "blit_state.txt" w]
    puts $d "E715=[format %02X%02X [debug read memory 0xE716] [debug read memory 0xE715]]"
    puts $d "E71A=[format %02X%02X [debug read memory 0xE71B] [debug read memory 0xE71A]]"
    close $d
    exit
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 18  { snap }
