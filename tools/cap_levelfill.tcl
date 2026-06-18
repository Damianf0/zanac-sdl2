# Captura el LEVEL-INIT del scroll: estado en la entrada de 0x9405 (RAM
# completa + HL=script ptr + IX + regs) y la RAM tras 0x946E (buffer 0xE800
# ya lleno con las 24 filas iniciales del mapa). -> lf_before.bin, lf_after.bin,
# lf_regs.txt
set ::armed 0
set ::phase 0
proc dumpram {fn} {
    set f [open $fn wb]; fconfigure $f -translation binary
    for {set a 0xE000} {$a < 0xEC00} {incr a} { puts -nonewline $f [binary format c [debug read memory $a]] }
    close $f
}
debug set_bp 0x9405 {$::armed} {
    if {$::phase==0} {
        set ::phase 1
        dumpram "lf_before.bin"
        set f [open "lf_regs.txt" w]
        foreach r {AF BC DE HL IX IY SP} { puts $f "$r=[format %04X [reg $r]]" }
        close $f
    }
}
# 0x427B = justo despues de CALL 0x946E (buffer lleno)
debug set_bp 0x427B {$::armed} {
    if {$::phase==1} { dumpram "lf_after.bin"; exit }
}
after time 8    { keymatrixdown 8 1 }
after time 8.2  { keymatrixup 8 1 }
after time 9    { keymatrixdown 8 1 }
after time 9.2  { keymatrixup 8 1 }
after time 8.5  { set ::armed 1 }
after time 20   { exit }
