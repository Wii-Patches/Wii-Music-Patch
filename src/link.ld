SECTIONS {
  . = BASE;
  .text : { *(.text .text.*) *(.rodata .rodata.* .rodata.cst*) *(.data .data.*) }
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) *(.sdata*) *(.sbss*) *(.bss) *(.PPC.EMB*) }
}
