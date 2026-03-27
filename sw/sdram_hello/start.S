.section .text.start
.global _start
_start:
    /* Stack in DMEM (0x80000000 + 8KB = 0x80002000), avoids SDRAM bus contention */
    li   sp, 0x80002000

    /* GPIO diagnostic: write 0xA (1010b) to gpio_out before any C code.
       GPIO output reg = 0xFFFC0000 + 4. If LEDs change, SDRAM execution works. */
    lui  t0, 0xFFFC0          /* t0 = 0xFFFC0000 */
    li   t1, 0xA              /* pattern 1010 → LED0,LED2 off; LED1,LED3 on */
    sw   t1, 4(t0)            /* *(0xFFFC0004) = 0xA */

    jal  main
1:  j 1b
