# Captura un call del command handler 0x95A8 (entrada) -> RET 0x95BF: RAM
# completa 0xE000-0xEBFF + regs antes, RAM despues, y marca si dispara el
# spawn 0x9B22. -> cmd_before.bin, cmd_after.bin, cmd_regs.txt
set ::armed 0
set ::phase 0
set ::spawn 0
proc dumpram {fn} {
    set f [open $fn wb]; fconfigure $f -translation binary
    for {set a 0xE000} {$a < 0xEC00} {incr a} { puts -nonewline $f [binary format c [debug read memory $a]] }
    close $f
}
debug set_bp 0x9B22 {$::armed} { if {$::phase==1} { set ::spawn 1 } }
debug set_bp 0x95A8 {$::armed} {
    if {$::phase==0} {
        set ::phase 1; set ::spawn 0
        dumpram "cmd_before.bin"
        set f [open "cmd_regs.txt" w]
        foreach r {AF BC DE HL IX IY} { puts $f "$r=[format %04X [reg $r]]" }
        close $f
    }
}
debug set_bp 0x95BF {$::armed} {
    if {$::phase==1} {
        dumpram "cmd_after.bin"
        set f [open "cmd_regs.txt" a]; puts $f "spawn_fired=$::spawn"; close $f
        exit
    }
}
after time 8    { keymatrixdown 8 1 }
after time 8.2  { keymatrixup 8 1 }
after time 9    { keymatrixdown 8 1 }
after time 9.2  { keymatrixup 8 1 }
after time 9.5  { set ::armed 1 }
after time 20   { exit }
