# Ubica el/los cargador(es) de VRAM: watchpoint en escrituras al puerto de
# datos del VDP (0x98). Acumula el PC de cada escritura durante el boot y al
# final vuelca un histograma por PC (las rutinas que llenan la VRAM).
# Salida -> trace_vdpwr_out.txt
array set ::cnt {}
set ::n 0
debug set_watchpoint write_io 0x98 {} {
    set pc [reg PC]
    incr ::cnt($pc)
    incr ::n
}
after time 6.5 {
    set out {}
    foreach pc [lsort -integer [array names ::cnt]] {
        lappend out [format "%04X  %d" $pc $::cnt($pc)]
    }
    set f [open "trace_vdpwr_out.txt" w]
    puts $f "total escrituras VDP: $::n"
    puts $f [join $out "\n"]
    close $f
    exit
}
