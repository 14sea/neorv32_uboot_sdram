OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY {
    SDRAM (rwx) : ORIGIN = 0x40000000, LENGTH = 32M
}

SECTIONS {
    . = 0x40000000;
    .text : {
        *(.text.start)
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
    } > SDRAM
    .data : { *(.data*) . = ALIGN(4); } > SDRAM
    .bss : { *(.bss*) . = ALIGN(4); } > SDRAM
    /* Stack is in DMEM (0x80002000), set in start.S - not here */
}
