# Ubica el DESCOMPRESOR: en cada OUT del loader (L5C07/L5BFC) lee la
# direccion de retorno en la pila (= PC del que lo llamo) y hace histograma.
# Salida -> trace_caller_out.txt
array set ::cnt {}
debug set_watchpoint write_io 0x98 {} {
    set pc [reg PC]
    if {$pc == 0x5C0D || $pc == 0x5C03} {
        set sp [reg SP]
        set ret [expr {[debug read memory [expr {$sp+2}]] | ([debug read memory [expr {$sp+3}]] << 8)}]
        incr ::cnt($ret)
    }
}
after time 6.5 {
    set out {}
    foreach r [lsort -integer [array names ::cnt]] {
        lappend out [format "%04X  %d" $r $::cnt($r)]
    }
    set f [open "trace_caller_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
