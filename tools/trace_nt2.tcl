# Traza COMPLETA de la name table: rastrea el ultimo SETWRT (cualquier dest)
# y en cada copia (LIT=0x5C10 / TILE=0x5BC0) loguea (lastdest, fuente). Asi
# se ve todo lo que arma la name table en orden, sin perder asociaciones.
# Captura las primeras 24 ops con dest en 0x3800-0x3AFF. -> trace_nt2_out.txt
set ::log {}
set ::dst 0
debug set_bp 0x0053 {} { set ::dst [reg HL] }
debug set_bp 0x5C10 {} {
    if {$::dst >= 0x3800 && $::dst < 0x3B00 && [llength $::log] < 24} {
        lappend ::log [format "%04X LIT src=%04X" $::dst [reg HL]]
    }
}
debug set_bp 0x5BC0 {} {
    if {$::dst >= 0x3800 && $::dst < 0x3B00 && [llength $::log] < 24} {
        lappend ::log [format "%04X TILE B=%02X tabHL=%04X" $::dst [reg B] [reg HL]]
    }
}
after time 6.5 {
    set f [open "trace_nt2_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
