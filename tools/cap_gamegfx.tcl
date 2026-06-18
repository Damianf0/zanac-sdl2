# Traza las fuentes ROM que el descompresor (0x5CDC, fuente=HL) procesa al
# entrar al gameplay (log armado DESPUES del titulo) y vuelca la VRAM de
# gameplay (patrones+sprites+color+nametable) como oraculo.
# -> gamegfx_src.txt, gamegfx_vram.bin
set ::armed 0
set ::log {}
debug set_bp 0x5CDC {$::armed} {
    if {[llength $::log] < 60} {
        lappend ::log [format "HL=%04X DE=%04X" [reg HL] [reg DE]]
    }
}
proc dumpvram {} {
    set f [open "gamegfx_vram.bin" wb]; fconfigure $f -translation binary
    for {set a 0x0000} {$a < 0x3B00} {incr a} { puts -nonewline $f [binary format c [debug read VRAM $a]] }
    close $f
}
after time 8    { keymatrixdown 8 1 }
after time 8.2  { keymatrixup 8 1 }
after time 9    { keymatrixdown 8 1 }
after time 9.2  { keymatrixup 8 1 }
after time 9.5  { set ::armed 1 }
after time 14   {
    set ::armed 0
    dumpvram
    set f [open "gamegfx_src.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
