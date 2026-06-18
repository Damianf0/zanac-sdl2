# Traza la FUENTE del cargador de VRAM: en cada OUT(C),A del loader (0x5C0C)
# registra HL (puntero fuente). Vuelca: cantidad por "region" de HL (ROM cart
# 0x4000-BFFF / RAM 0xC000+ / BIOS <0x4000), el rango min/max, y las primeras
# 40 muestras (HL, byte escrito). Salida -> trace_src_out.txt
set ::log {}
set ::n 0
array set ::reg {rom 0 ram 0 bios 0}
set ::minhl 0xFFFF
set ::maxhl 0
debug set_watchpoint write_io 0x98 {} {
    set pc [reg PC]
    if {$pc == 0x5C0D || $pc == 0x5C03} {
        set hl [reg HL]
        incr ::n
        if {$hl >= 0x4000 && $hl < 0xC000} { incr ::reg(rom) } \
        elseif {$hl >= 0xC000} { incr ::reg(ram) } \
        else { incr ::reg(bios) }
        if {$hl < $::minhl} { set ::minhl $hl }
        if {$hl > $::maxhl} { set ::maxhl $hl }
        if {[llength $::log] < 40} {
            lappend ::log [format "HL=%04X val=%02X" $hl [reg A]]
        }
    }
}
after time 6.5 {
    set f [open "trace_src_out.txt" w]
    puts $f "OUT del loader: $::n   (HL en ROM=$::reg(rom) RAM=$::reg(ram) BIOS=$::reg(bios))"
    puts $f [format "rango HL: %04X - %04X" $::minhl $::maxhl]
    puts $f [join $::log "\n"]
    close $f
    exit
}
