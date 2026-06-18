# Oraculo de desensamblado: carga zanac.rom como cartucho y desensambla desde
# 0x4010 avanzando por la longitud que reporta openMSX. Vuelca "addr len mnem"
# por instruccion -> dis_oracle_out.txt. Se compara contra tools/z80dis.py.
proc dump {} {
    set addr 0x4010
    set out {}
    for {set i 0} {$i < 600} {incr i} {
        set r [debug disasm $addr]
        set len [expr {[llength $r] - 1}]
        set mnem [lindex $r 0]
        lappend out [format "%04X %d %s" $addr $len $mnem]
        set addr [expr {$addr + $len}]
        if {$addr >= 0xC000} break
    }
    set f [open "dis_oracle_out.txt" w]; puts $f [join $out "\n"]; close $f
    exit
}
# capturar al entrar a INIT (el cartucho ya está mapeado en 0x4000-0xBFFF)
debug set_bp 0x4010 {} { dump }
after time 10 {
    set f [open "dis_oracle_out.txt" w]; puts $f "TIMEOUT byte@4010=[debug read memory 0x4010]"; close $f
    exit
}
