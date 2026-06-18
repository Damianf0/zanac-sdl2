# Traza la ORQUESTACION de la carga del titulo, en orden:
#  - SETWRT (BIOS 0x53): destino VRAM (HL) -> "DST hhhh"
#  - entry del descompresor (0x5CDC): fuente (HL) + retorno -> "DEC src=.. ret=.."
#  - entry copia literal 0x00-term (0x5C10): fuente (HL) -> "LIT src=.."
# Salida -> trace_orch_out.txt
set ::log {}
debug set_bp 0x0053 {} {
    if {[llength $::log] < 80} { lappend ::log [format "DST %04X" [reg HL]] }
}
debug set_bp 0x5CDC {} {
    set sp [reg SP]
    set ret [expr {[debug read memory $sp] | ([debug read memory [expr {$sp+1}]] << 8)}]
    if {[llength $::log] < 80} { lappend ::log [format "DEC src=%04X ret=%04X" [reg HL] $ret] }
}
debug set_bp 0x5C10 {} {
    if {[llength $::log] < 80} { lappend ::log [format "LIT src=%04X" [reg HL]] }
}
after time 6.5 {
    set f [open "trace_orch_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
