/* Diagnostic: test SDRAM execution with UART markers at each step */
    .section .text
    .global _start

_start:
    /* Step 0: UART base + long drain delay */
    lui     t0, 0xFFF50        /* t0 = 0xFFF50000 UART base, KEEP in t0 */

    /* 40ms drain (2M cycles) */
    lui     t2, 0x1F4
    addi    t2, t2, 0x240      /* ~2000000 */
1:  addi    t2, t2, -1
    bnez    t2, 1b

    /* Step 1: send 'A' — proves instruction fetch works */
    li      t1, 'A'
    sw      t1, 4(t0)
    /* Delay for TX */
    li      t2, 50000
2:  addi    t2, t2, -1
    bnez    t2, 2b

    /* Step 2: send 'B' — proves we got past cache line boundary */
    li      t1, 'B'
    sw      t1, 4(t0)
    li      t2, 50000
3:  addi    t2, t2, -1
    bnez    t2, 3b

    /* Step 3: SDRAM write test */
    li      s0, 0x41000000     /* Use high SDRAM address (far from code) */
    li      t3, 0x12345678
    sw      t3, 0(s0)

    /* send 'C' — proves SDRAM write didn't hang */
    li      t1, 'C'
    sw      t1, 4(t0)
    li      t2, 50000
4:  addi    t2, t2, -1
    bnez    t2, 4b

    /* Step 4: SDRAM read test */
    lw      t4, 0(s0)

    /* send 'D' — proves SDRAM read didn't hang */
    li      t1, 'D'
    sw      t1, 4(t0)
    li      t2, 50000
5:  addi    t2, t2, -1
    bnez    t2, 5b

    /* Step 5: compare */
    bne     t3, t4, fail
    li      t1, '='            /* pass */
    sw      t1, 4(t0)
    j       done

fail:
    li      t1, 'X'            /* fail */
    sw      t1, 4(t0)

done:
    li      t2, 50000
6:  addi    t2, t2, -1
    bnez    t2, 6b

    /* CR LF */
    li      t1, '\r'
    sw      t1, 4(t0)
    li      t2, 50000
7:  addi    t2, t2, -1
    bnez    t2, 7b
    li      t1, '\n'
    sw      t1, 4(t0)

    /* Blink LED */
    li      t0, 0xFFFC0000
    li      t1, 1
8:  sw      t1, 4(t0)
    li      t2, 2500000
9:  addi    t2, t2, -1
    bnez    t2, 9b
    xori    t1, t1, 1
    j       8b
