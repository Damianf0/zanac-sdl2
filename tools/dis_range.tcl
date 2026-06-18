# Desensambla un rango con openMSX (cartucho ya mapeado en el bp de INIT).
# Rango fijo: 0x5CC0 - 0x5D2C (el descompresor del título). -> dis_range_out.txt
proc dump {} {
    set addr 0x5CC0
    set out {}
    while {$addr <= 0x5D2C} {
        set r [debug disasm $addr]
        set len [expr {[llength $r] - 1}]
        set bytes ""
        for {set i 1} {$i <= $len} {incr i} {
            append bytes [format "%02X " [lindex $r $i]]
        }
        lappend out [format "%04X  %-12s %s" $addr $bytes [lindex $r 0]]
        set addr [expr {$addr + $len}]
    }
    set f [open "dis_range_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
debug set_bp 0x4010 {} { dump }
after time 10 { exit }
