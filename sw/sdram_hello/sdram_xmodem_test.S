/* SDRAM R/W test at multiple addresses. Delay-based UART. */
    .section .text
    .global _start

_start:
    li      t0, 0xFFF50000     /* UART base */

    /* 20ms drain */
    li      t2, 1000000
1:  addi    t2, t2, -1
    bnez    t2, 1b

    /* Test 1: write/read at 0x40000100 (known-good area, same as stage2 test) */
    li      s0, 0x40000100
    li      t3, 0xCAFEBABE
    sw      t3, 0(s0)
    /* delay before read */
    li      t2, 1000
2:  addi    t2, t2, -1
    bnez    t2, 2b
    lw      t4, 0(s0)
    bne     t3, t4, fail1

    li      t1, '1'
    sw      t1, 4(t0)
    li      t2, 100000
3:  addi    t2, t2, -1
    bnez    t2, 3b

    /* Test 2: write/read at 0x40100000 (1 MB offset) */
    li      s0, 0x40100000
    li      t3, 0x12345678
    sw      t3, 0(s0)
    li      t2, 1000
4:  addi    t2, t2, -1
    bnez    t2, 4b
    lw      t4, 0(s0)
    bne     t3, t4, fail2

    li      t1, '2'
    sw      t1, 4(t0)
    li      t2, 100000
5:  addi    t2, t2, -1
    bnez    t2, 5b

    /* Test 3: write/read at 0x402FFFFC (where SP test was) */
    li      s0, 0x402FFFFC
    li      t3, 0xDEADBEEF
    sw      t3, 0(s0)
    li      t2, 1000
6:  addi    t2, t2, -1
    bnez    t2, 6b
    lw      t4, 0(s0)
    bne     t3, t4, fail3

    li      t1, '3'
    sw      t1, 4(t0)
    li      t2, 100000
7:  addi    t2, t2, -1
    bnez    t2, 7b

    /* All pass */
    li      t1, '\r'
    sw      t1, 4(t0)
    li      t2, 100000
8:  addi    t2, t2, -1
    bnez    t2, 8b
    li      t1, '\n'
    sw      t1, 4(t0)
    j       blink

fail1:
    li      t1, 'X'
    sw      t1, 4(t0)
    li      t2, 100000
9:  addi    t2, t2, -1
    bnez    t2, 9b
    li      t1, '1'
    sw      t1, 4(t0)
    j       blink
fail2:
    li      t1, 'X'
    sw      t1, 4(t0)
    li      t2, 100000
10: addi    t2, t2, -1
    bnez    t2, 10b
    li      t1, '2'
    sw      t1, 4(t0)
    j       blink
fail3:
    li      t1, 'X'
    sw      t1, 4(t0)
    li      t2, 100000
11: addi    t2, t2, -1
    bnez    t2, 11b
    li      t1, '3'
    sw      t1, 4(t0)
    j       blink

blink:
    li      t0, 0xFFFC0000
    li      t1, 1
12: sw      t1, 4(t0)
    li      t2, 2500000
13: addi    t2, t2, -1
    bnez    t2, 13b
    slli    t1, t1, 1
    andi    t3, t1, 15
    bnez    t3, 12b
    li      t1, 1
    j       12b
