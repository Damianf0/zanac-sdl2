# Captura un pase COMPLETO del expansor de runs (0x99F7 entrada -> 0x9A67 RET).
# Vuelca RAM 0xE000-0xEBFF + registros ANTES (0x99F7) y RAM DESPUES (0x9A67),
# marcando si se invocó el handler de comandos 0x95A8 en el medio (para elegir
# un pase "limpio" sin comando). -> exp_before.bin, exp_after.bin, exp_regs.txt
set ::armed 0
set ::phase 0   ;# 0=esperando entrada, 1=esperando salida
set ::cmd 0

proc dumpram {fn} {
    set f [open $fn wb]; fconfigure $f -translation binary
    for {set a 0xE000} {$a < 0xEC00} {incr a} { puts -nonewline $f [binary format c [debug read memory $a]] }
    close $f
}

debug set_bp 0x95A8 {$::armed} { if {$::phase==1} { set ::cmd 1 } }

debug set_bp 0x99F7 {$::armed} {
    if {$::phase==0} {
        set ::phase 1
        set ::cmd 0
        dumpram "exp_before.bin"
        set f [open "exp_regs.txt" w]
        puts $f "A=[format %02X [expr {([reg AF]>>8)&0xFF}]]"
        puts $f "BC=[format %04X [reg BC]]"
        puts $f "DE=[format %04X [reg DE]]"
        puts $f "HL=[format %04X [reg HL]]"
        puts $f "IX=[format %04X [reg IX]]"
        puts $f "IY=[format %04X [reg IY]]"
        puts $f "E715=[format %02X%02X [debug read memory 0xE716] [debug read memory 0xE715]]"
        close $f
    }
}

debug set_bp 0x9A67 {$::armed} {
    if {$::phase==1} {
        dumpram "exp_after.bin"
        set f [open "exp_regs.txt" a]
        puts $f "cmd_fired=$::cmd"
        close $f
        exit
    }
}

after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 12  { set ::armed 1 }
after time 20  { exit }
