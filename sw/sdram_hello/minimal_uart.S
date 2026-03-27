/* Minimal SDRAM execution test: one UART char + blink LED */
    .section .text
    .global _start

_start:
    /* Write 'H' to UART TX register (0xFFF50004) */
    lui     t0, 0xFFF50        /* t0 = 0xFFF50000 (UART base) */
    li      t1, 0x48           /* 'H' = 0x48 */
    sw      t1, 4(t0)         /* UART0_RTX = 'H' */

    /* Small delay */
    li      t2, 500000
1:  addi    t2, t2, -1
    bnez    t2, 1b

    /* Write 'i' */
    li      t1, 0x69           /* 'i' */
    sw      t1, 4(t0)

    /* Blink LED0 forever via GPIO */
    li      t0, 0xFFFC0000     /* GPIO base */
    li      t1, 1
2:  sw      t1, 4(t0)         /* gpio_o = 1 */
    li      t2, 2500000
3:  addi    t2, t2, -1
    bnez    t2, 3b
    xori    t1, t1, 1
    j       2b
