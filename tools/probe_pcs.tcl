# Cuenta cuántas veces se ejecutan PCs clave del motor de scroll durante
# gameplay (t=11..18). -> probe_pcs_out.txt
foreach pc {0x98B0 0x98D4 0x99D2 0x99F7 0x99FD 0x9A30 0x9A80 0x95A8 0x9B22 0x986E} {
    set ::c($pc) 0
    debug set_bp $pc {$::armed} "incr ::c($pc)"
}
set ::armed 0
after time 8   { keymatrixdown 8 1 }
after time 8.2 { keymatrixup 8 1 }
after time 9   { keymatrixdown 8 1 }
after time 9.2 { keymatrixup 8 1 }
after time 11  { set ::armed 1 }
after time 18  {
    set f [open "probe_pcs_out.txt" w]
    foreach pc {0x98B0 0x98D4 0x99D2 0x99F7 0x99FD 0x9A30 0x9A80 0x95A8 0x9B22 0x986E} {
        puts $f "$pc -> $::c($pc)"
    }
    close $f
    exit
}
