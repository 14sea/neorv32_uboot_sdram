/* Test: isolate D-bus SDRAM read */
    .section .text
    .global _start

_start:
    lui     t0, 0xFFF50        /* UART base */

    /* 40ms drain */
    lui     t2, 0x1F4
    addi    t2, t2, 0x240
1:  addi    t2, t2, -1
    bnez    t2, 1b

    /* 'A' — alive */
    li      t1, 'A'
    sw      t1, 4(t0)
    li      t2, 50000
2:  addi    t2, t2, -1
    bnez    t2, 2b

    /* Read from own code (0x40000000) — known value 0xFFF502B7 */
    lui     s0, 0x40000
    lw      t4, 0(s0)         /* D-bus read from SDRAM */

    /* 'B' — read completed */
    li      t1, 'B'
    sw      t1, 4(t0)
    li      t2, 50000
3:  addi    t2, t2, -1
    bnez    t2, 3b

    /* Check if t4 == 0xFFF502B7 */
    lui     t3, 0xFFF50
    addi    t3, t3, 0x2B7
    bne     t3, t4, fail

    /* '=' — pass */
    li      t1, '='
    sw      t1, 4(t0)
    j       done

fail:
    /* 'X' — fail, also dump what we got */
    li      t1, 'X'
    sw      t1, 4(t0)

done:
    li      t2, 50000
4:  addi    t2, t2, -1
    bnez    t2, 4b
    li      t1, '\r'
    sw      t1, 4(t0)
    li      t2, 50000
5:  addi    t2, t2, -1
    bnez    t2, 5b
    li      t1, '\n'
    sw      t1, 4(t0)

    /* Blink */
    li      t0, 0xFFFC0000
    li      t1, 1
6:  sw      t1, 4(t0)
    li      t2, 2500000
7:  addi    t2, t2, -1
    bnez    t2, 7b
    xori    t1, t1, 1
    j       6b
