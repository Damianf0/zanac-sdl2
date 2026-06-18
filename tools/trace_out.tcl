# Captura el STREAM DE SALIDA del descompresor del titulo: el valor (A) de
# cada OUT del loader (PC 5C0D=L5C07 o 5C03=L5BFC), en orden, durante el boot.
# -> trace_out_out.txt (un byte hex por linea). Es la concatenacion de las
# salidas de las 13 invocaciones; el port en C debe reproducirlo.
set ::log {}
debug set_watchpoint write_io 0x98 {} {
    set pc [reg PC]
    if {$pc == 0x5C0D || $pc == 0x5C03} {
        lappend ::log [format %02X [reg A]]
    }
}
after time 6.5 {
    set f [open "trace_out_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
