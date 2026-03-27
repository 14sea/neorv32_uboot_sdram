/* Diagnostic: runs from SDRAM, stack in DMEM, GPIO + UART tests */
#include <stdint.h>

#define UART0_CTRL  (*(volatile uint32_t *)0xFFF50000UL)
#define UART0_DATA  (*(volatile uint32_t *)0xFFF50004UL)
#define GPIO_OUTPUT (*(volatile uint32_t *)0xFFFC0004UL)

/* 115200 @ 50 MHz: prsc=0 (div2), baud_val=216 → bits[15:6]=216, bit0=1 → 0x3601 */
#define UART_CTRL_VAL 0x3601

static void delay(volatile uint32_t n) { while (n--); }

static void uart_putc_nowait(char c) {
    /* Write directly to DATA without checking TX_NFULL - tests if UART write path works */
    UART0_DATA = (uint32_t)(uint8_t)c;
}

static void uart_putc(char c) {
    /* Wait for TX not full (bit 19 = TX_NFULL) */
    while (!(UART0_CTRL & (1u << 19)));
    UART0_DATA = (uint32_t)(uint8_t)c;
}

static void uart_puts(const char *s) { while (*s) uart_putc(*s++); }

static void uart_puthex32(uint32_t v) {
    const char *hex = "0123456789abcdef";
    uart_puts("0x");
    for (int i = 28; i >= 0; i -= 4)
        uart_putc(hex[(v >> i) & 0xF]);
}

void main(void) {
    /*
     * PHASE 1: GPIO diagnostic (no UART, no wait loops)
     * If gpio_out changes to 0x5 (0101), C entry point reached.
     */
    GPIO_OUTPUT = 0x5;   /* 0101 → LED0,LED2 on; LED1,LED3 off */

    /*
     * PHASE 2: Unconditional UART writes (no TX_NFULL poll)
     * Re-init UART then blast bytes directly. If any character appears on
     * the terminal, the UART write path works but TX_NFULL polling was stuck.
     */
    UART0_CTRL = UART_CTRL_VAL;  /* re-init: prsc=0, baud=216, enable */
    uart_putc_nowait('S');
    uart_putc_nowait('D');
    uart_putc_nowait('R');
    uart_putc_nowait('A');
    uart_putc_nowait('M');
    uart_putc_nowait('\r');
    uart_putc_nowait('\n');

    /* PHASE 3: GPIO shows we survived past the unconditional UART writes */
    GPIO_OUTPUT = 0x3;   /* 0011 → LED0,LED1 on; LED2,LED3 off */
    delay(500000);       /* short delay */

    /*
     * PHASE 4: Polled UART (normal TX_NFULL wait)
     */
    UART0_CTRL = UART_CTRL_VAL;
    delay(100);          /* brief pause after UART reset */
    uart_puts("\r\n[sdram] Hello from SDRAM!\r\n");

    /* Print some register values for debug */
    uart_puts("[sdram] UART_CTRL=");
    uart_puthex32(UART0_CTRL);
    uart_puts("\r\n");
    uart_puts("[sdram] sp=");
    uint32_t sp_val;
    __asm__ volatile ("mv %0, sp" : "=r"(sp_val));
    uart_puthex32(sp_val);
    uart_puts(" (should be near 0x80002000)\r\n");

    /* GPIO shows we reached the polled UART section */
    GPIO_OUTPUT = 0xF;   /* all off */

    uint32_t ctr = 0;
    for (;;) {
        delay(2000000);
        uart_puts("[sdram] tick ");
        uart_puthex32(ctr++);
        uart_puts("\r\n");
        GPIO_OUTPUT = ctr & 0xF;  /* LED pattern counts up */
    }
}
