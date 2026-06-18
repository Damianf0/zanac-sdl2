# Halla la fuente del LDIRVM de la name table: cuando el loop BIOS (pc 02A5)
# escribe el primer byte (addr==0x3800), loguea HL (= puntero fuente, ROM o
# RAM) y BC (cuenta). Tambien la fuente de cada LDIRVM a 0x3800. -> trace_ntsrc_out.txt
set ::latch {}
set ::addr 0
set ::log {}
debug set_watchpoint write_io 0x99 {} {
    lappend ::latch $::wp_last_value
    if {[llength $::latch] >= 2} {
        set ::addr [expr {[lindex $::latch 0] | (([lindex $::latch 1] & 0x3F) << 8)}]
        set ::latch {}
    }
}
debug set_watchpoint write_io 0x98 {} {
    if {$::addr == 0x3800 && [llength $::log] < 8} {
        lappend ::log [format "HL=%04X BC=%04X pc=%04X (HL en %s)" [reg HL] [reg BC] [reg PC] \
            [expr {[reg HL] >= 0xC000 ? "RAM" : ([reg HL] >= 0x4000 ? "ROM" : "BIOS")}]]
    }
    set ::addr [expr {($::addr + 1) & 0x3FFF}]
}
after time 6.5 {
    set f [open "trace_ntsrc_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
