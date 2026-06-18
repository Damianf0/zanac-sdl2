# Traza las llamadas a LDIRVM (BIOS 0x5C) con destino en la name table:
# HL=fuente, DE=destino VRAM, BC=cuenta. Para hallar la carga base de la
# name table (768 bytes). -> trace_ldir_out.txt
set ::log {}
debug set_bp 0x005C {} {
    set de [reg DE]
    if {$de >= 0x3800 && $de < 0x3B00 && [llength $::log] < 20} {
        lappend ::log [format "src=%04X dst=%04X len=%04X" [reg HL] $de [reg BC]]
    }
}
after time 6.5 {
    set f [open "trace_ldir_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
