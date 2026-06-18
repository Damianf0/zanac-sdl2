# Ubica la rutina de render del scroll: histograma del PC de las escrituras
# a la name table (0x3800-3AFF) durante el gameplay, y el retorno en pila
# (por si el OUT es un primitivo compartido). -> probe_scrollpc_out.txt
set ::latch {}
set ::addr 0
array set ::pc {}
array set ::ret {}
set ::on 0
debug set_watchpoint write_io 0x99 {} {
    lappend ::latch $::wp_last_value
    if {[llength $::latch] >= 2} {
        set ::addr [expr {[lindex $::latch 0] | (([lindex $::latch 1] & 0x3F) << 8)}]
        set ::latch {}
    }
}
debug set_watchpoint write_io 0x98 {} {
    if {$::on && $::addr >= 0x3800 && $::addr < 0x3B00} {
        incr ::pc([reg PC])
        set sp [reg SP]
        set r [expr {[debug read memory $sp] | ([debug read memory [expr {$sp+1}]] << 8)}]
        incr ::ret($r)
    }
    set ::addr [expr {($::addr + 1) & 0x3FFF}]
}
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::on 1 }
after time 13  {
    set ::on 0
    set out {}
    lappend out "PC de escrituras a name table:"
    foreach k [lsort -integer [array names ::pc]] { lappend out [format "  PC %04X x%d" $k $::pc($k)] }
    lappend out "retornos en pila (top callers):"
    foreach k [lsort -integer [array names ::ret]] { lappend out [format "  ret %04X x%d" $k $::ret($k)] }
    set f [open "probe_scrollpc_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
