# Captura un REBUILD completo del scroll (entry 0x9888 -> RET 0x9A67):
# prólogo + driver loop (0x98D4, bloque E2C0) + fetch (0x99D2) + expansor.
# Vuelca RAM 0xE000-0xEBFF + registros ANTES (0x9888) y RAM DESPUES (0x9A67),
# marcando si se invocaron los caminos complejos (comando 0x95A8, recarga
# 0x95ED, spawn 0x9B22) para elegir un tick "limpio".
# -> tick_before.bin, tick_after.bin, tick_regs.txt
set ::armed 0
set ::phase 0
set ::cx 0

proc dumpram {fn} {
    set f [open $fn wb]; fconfigure $f -translation binary
    for {set a 0xE000} {$a < 0xEC00} {incr a} { puts -nonewline $f [binary format c [debug read memory $a]] }
    close $f
}

foreach pc {0x95A8 0x95ED 0x9B22} {
    debug set_bp $pc {$::armed} { if {$::phase==1} { incr ::cx } }
}

debug set_bp 0x9888 {$::armed} {
    if {$::phase==0} {
        set ::phase 1; set ::cx 0
        dumpram "tick_before.bin"
        set f [open "tick_regs.txt" w]
        foreach r {AF BC DE HL IX IY} { puts $f "$r=[format %04X [reg $r]]" }
        puts $f "E702=[format %02X [debug read memory 0xE702]]"
        close $f
    }
}

debug set_bp 0x9A67 {$::armed} {
    if {$::phase==1} {
        dumpram "tick_after.bin"
        set f [open "tick_regs.txt" a]; puts $f "complex_fired=$::cx"; close $f
        exit
    }
}

after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 12  { set ::armed 1 }
after time 20  { exit }
