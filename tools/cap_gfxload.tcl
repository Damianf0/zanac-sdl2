# Traza TODAS las llamadas al descompresor 0x5CDC (fuente=HL, dest por SETWRT)
# desde el boot hasta el gameplay, con timestamp, para separar las del titulo
# de las del nivel. -> gfxload_out.txt
set ::log {}
debug set_bp 0x5CDC {} {
    if {[llength $::log] < 80} {
        lappend ::log [format "t=%.1f HL=%04X" [machine_info time] [reg HL]]
    }
}
after time 8    { keymatrixdown 8 1 }
after time 8.2  { keymatrixup 8 1 }
after time 9    { keymatrixdown 8 1 }
after time 9.2  { keymatrixup 8 1 }
after time 12   {
    set f [open "gfxload_out.txt" w]; puts $f [join $::log "\n"]; close $f
    exit
}
