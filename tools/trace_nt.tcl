# Traza la construccion de la NAME TABLE (0x3800-0x3AFF): SETWRT con destino
# en ese rango, y la copia que sigue (LIT = L5C10 0x00-term, o TILE = rutina
# 0x5BC0 que lee de la tabla 0x4827). Captura las primeras 60 ops. Marca el
# destino "pendiente" para asociarlo con la copia siguiente.
# Salida -> trace_nt_out.txt
set ::log {}
set ::pend ""
debug set_bp 0x0053 {} {
    set hl [reg HL]
    if {$hl >= 0x3800 && $hl < 0x3B00} { set ::pend [format %04X $hl] }
}
debug set_bp 0x5C10 {} {
    if {$::pend ne "" && [llength $::log] < 60} {
        lappend ::log [format "DST %s  LIT src=%04X" $::pend [reg HL]]; set ::pend ""
    }
}
debug set_bp 0x5BC0 {} {
    if {$::pend ne "" && [llength $::log] < 60} {
        lappend ::log [format "DST %s  TILE B=%02X HL=%04X" $::pend [reg B] [reg HL]]; set ::pend ""
    }
}
after time 6.5 {
    set f [open "trace_nt_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
