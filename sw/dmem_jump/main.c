// dmem_jump/main.c — DMEM + SDRAM execution test with XBUS debug LEDs
//
// Test 1: Copy payload to DMEM, call it (already proven to work)
// Test 2: Copy payload to SDRAM (0x40000000), verify via D-bus, then jump
//         Debug LEDs on board show XBUS activity:
//           LED0: any XBUS request seen (sticky)
//           LED1: SDRAM-addressed request seen (sticky)
//           LED2: SDRAM ACK completed (sticky)
//           LED3: currently pending (live — stuck = problem)

#include <neorv32.h>

#define BAUD_RATE 115200

#define DMEM_PAYLOAD_ADDR   0x80001800
#define SDRAM_PAYLOAD_ADDR  0x40000000

// Payload: set GPIO=0x5, send 'D' to UART, return
static const uint32_t payload[] = {
    0xFFFC02B7,  // lui  t0, 0xFFFC0
    0x00500313,  // addi t1, x0, 5
    0x0062A223,  // sw   t1, 4(t0)
    0xFFF502B7,  // lui  t0, 0xFFF50
    0x04400313,  // addi t1, x0, 0x44  ('D')
    0x0062A223,  // sw   t1, 4(t0)
    0x00008067,  // ret
};

static int copy_and_verify(volatile uint32_t *dst, const char *name) {
    neorv32_uart0_printf("[test] Copying %u bytes to %s...\n",
        (uint32_t)sizeof(payload), name);
    for (unsigned i = 0; i < sizeof(payload) / 4; i++) {
        dst[i] = payload[i];
    }
    for (unsigned i = 0; i < sizeof(payload) / 4; i++) {
        if (dst[i] != payload[i]) {
            neorv32_uart0_printf("[test] VERIFY FAIL word %u: 0x%x != 0x%x\n",
                i, dst[i], payload[i]);
            return 0;
        }
    }
    neorv32_uart0_printf("[test] Verify OK\n");
    return 1;
}

int main(void) {
    neorv32_rte_setup();
    neorv32_uart0_setup(BAUD_RATE, 0);

    neorv32_uart0_printf("\n=== XBUS Debug LED Test ===\n");
    neorv32_uart0_printf("LED0=any_xbus  LED1=sdram_req  LED2=sdram_ack  LED3=pending\n\n");

    // ── Test 1: DMEM ──
    neorv32_uart0_printf("--- Test 1: DMEM execution ---\n");
    if (!copy_and_verify((volatile uint32_t *)DMEM_PAYLOAD_ADDR, "DMEM 0x80001800"))
        goto halt;

    asm volatile ("fence.i");
    neorv32_uart0_printf("[test] Calling DMEM payload...\n");
    ((void (*)(void))DMEM_PAYLOAD_ADDR)();
    neorv32_uart0_printf("[test] DMEM OK (returned)\n\n");

    // ── Test 2: SDRAM ──
    neorv32_uart0_printf("--- Test 2: SDRAM execution ---\n");
    neorv32_uart0_printf("[test] Writing payload to SDRAM 0x40000000 (D-bus)...\n");
    if (!copy_and_verify((volatile uint32_t *)SDRAM_PAYLOAD_ADDR, "SDRAM 0x40000000"))
        goto halt;

    // At this point, LED0 and LED1 should already be ON (D-bus SDRAM write/read)
    neorv32_uart0_printf("[test] D-bus SDRAM access done. Check LEDs:\n");
    neorv32_uart0_printf("[test]   LED0 (any_xbus)  = should be ON\n");
    neorv32_uart0_printf("[test]   LED1 (sdram_req) = should be ON\n");
    neorv32_uart0_printf("[test]   LED2 (sdram_ack) = should be ON\n");
    neorv32_uart0_printf("[test]   LED3 (pending)   = should be OFF\n\n");

    neorv32_uart0_printf("[test] About to jump to SDRAM 0x40000000 (I-bus fetch)...\n");
    neorv32_uart0_printf("[test] If CPU hangs, check LED3 (pending=stuck)\n");

    // Small delay so UART finishes transmitting
    for (volatile uint32_t d = 0; d < 500000; d++) {}

    asm volatile ("fence.i");
    ((void (*)(void))SDRAM_PAYLOAD_ADDR)();

    // If we get here, SDRAM execution worked!
    neorv32_uart0_printf("\n[test] === SDRAM EXECUTION OK! ===\n");
    goto blink;

halt:
    neorv32_uart0_printf("[test] HALTED\n");
    while (1) {}

blink:
    {
        uint32_t cnt = 0;
        while (1) {
            neorv32_uart0_printf("[test] tick %u\n", cnt++);
            for (volatile uint32_t d = 0; d < 5000000; d++) {}
        }
    }
    return 0;
}
