# Sondea el arranque: a varios tiempos, vuelca un resumen de la name table
# (cuántos tiles no-cero) y los registros VDP, para ver el flujo
# boot -> logo -> título -> demo. Salida -> probe_boot_out.txt
set ::log {}
proc snap {t} {
    set nb 0
    # name table en 0x3800 (R2=0x0E): 768 entradas
    for {set i 0} {$i < 768} {incr i} {
        if {[debug read VRAM [expr {0x3800 + $i}]] != 0} { incr nb }
    }
    set r1 [debug read "VDP regs" 1]
    lappend ::log [format "t=%ss  name_nonzero=%d/768  R1=%02X (screen=%s)" \
        $t $nb $r1 [expr {($r1 & 0x40) ? "ON" : "off"}]]
}
after time 3  { snap 3 }
after time 6  { snap 6 }
after time 9  { snap 9 }
after time 12 { snap 12 }
after time 15 {
    snap 15
    set f [open "probe_boot_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
