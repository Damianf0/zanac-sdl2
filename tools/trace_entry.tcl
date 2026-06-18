# Captura los parametros de cada invocacion del descompresor del titulo:
# breakpoint en 0x5CDC (LD E,A = entry, una vez por llamada). Loguea
# HL (fuente ROM), D (byte escape), A (flag E inicial). -> trace_entry_out.txt
set ::log {}
debug set_bp 0x5CDC {} {
    lappend ::log [format "HL=%04X D=%02X A=%02X" [reg HL] [reg D] [reg A]]
}
after time 6.5 {
    set f [open "trace_entry_out.txt" w]
    puts $f "invocaciones: [llength $::log]"
    puts $f [join $::log "\n"]
    close $f
    exit
}
