// SPDX-License-Identifier: GPL-2.0+
/*
 * stage2_loader — NEORV32 xmodem receiver for U-Boot
 */

#include <neorv32.h>
#include <stdint.h>

#define UBOOT_LOAD_ADDR  0x40000000UL
#define UART_BAUD        115200

#define SOH   0x01
#define EOT   0x04
#define ACK   0x06
#define NAK   0x15
#define CAN   0x18

#define XMODEM_BLOCK_SIZE  128
#define XMODEM_TIMEOUT_MS  3000
#define XMODEM_RETRY_MAX   20

static void uart_putc(char c)  { neorv32_uart0_putc(c); }
static void uart_puts(const char *s) { while (*s) uart_putc(*s++); }

static void uart_puthex32(uint32_t v)
{
    const char hex[] = "0123456789abcdef";
    uart_puts("0x");
    for (int i = 28; i >= 0; i -= 4)
        uart_putc(hex[(v >> i) & 0xF]);
}

static int uart_getc_timeout(uint32_t timeout_ms)
{
    uint32_t cycles_per_ms = neorv32_sysinfo_get_clk() / 1000;
    uint64_t deadline = neorv32_cpu_get_cycle()
                      + (uint64_t)timeout_ms * cycles_per_ms;
    while (neorv32_cpu_get_cycle() < deadline) {
        if (neorv32_uart0_char_received())
            return (int)(uint8_t)neorv32_uart0_char_received_get();
    }
    return -1;
}

/* Simple SDRAM test: write pattern, read back */
static int sdram_test(void)
{
    volatile uint32_t *base = (volatile uint32_t *)UBOOT_LOAD_ADDR;
    uint32_t n = 64;

    uart_puts("[stage2] SDRAM word-write test...\r\n");
    for (uint32_t i = 0; i < n; i++)
        base[i] = 0xDEAD0000 | i;

    uint32_t errors = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t got = base[i];
        uint32_t exp = 0xDEAD0000 | i;
        if (got != exp) {
            uart_puts("  FAIL["); uart_puthex32(i);
            uart_puts("]: exp="); uart_puthex32(exp);
            uart_puts(" got="); uart_puthex32(got);
            uart_puts("\r\n");
            errors++;
            if (errors > 4) break;
        }
    }
    if (errors == 0) {
        uart_puts("[stage2] SDRAM test PASS\r\n");
        return 1;
    }
    return 0;
}

static uint32_t xmodem_receive(uint8_t *dest)
{
    uint8_t blk_num = 1;
    uint32_t total  = 0;
    int retries     = 0;

    uart_putc(NAK);

    while (1) {
        int c = uart_getc_timeout(XMODEM_TIMEOUT_MS);

        if (c < 0) {
            retries++;
            if (retries > XMODEM_RETRY_MAX) {
                uart_putc(CAN); uart_putc(CAN);
                uart_puts("\r\n[!] xmodem timeout\r\n");
                return 0;
            }
            uart_puts("\r\n[stage2] waiting for sender (NAK)...\r\n");
            uart_putc(NAK);
            continue;
        }

        if (c == EOT) { uart_putc(ACK); return total; }
        if (c == CAN) { uart_puts("\r\n[!] xmodem cancelled\r\n"); return 0; }
        if (c != SOH) continue;

        int bn  = uart_getc_timeout(1000);
        int bnc = uart_getc_timeout(1000);
        if (bn < 0 || bnc < 0) { uart_putc(NAK); continue; }

        uint8_t buf[XMODEM_BLOCK_SIZE];
        uint8_t csum = 0;
        int ok = 1;
        for (int i = 0; i < XMODEM_BLOCK_SIZE; i++) {
            int b = uart_getc_timeout(1000);
            if (b < 0) { ok = 0; break; }
            buf[i] = (uint8_t)b;
            csum  += (uint8_t)b;
        }
        if (!ok) { uart_putc(NAK); continue; }

        int recv_csum = uart_getc_timeout(1000);
        if (recv_csum < 0) { uart_putc(NAK); continue; }

        if ((uint8_t)bn != blk_num || (uint8_t)bnc != (uint8_t)(~blk_num) ||
            (uint8_t)recv_csum != csum) {
            retries++;
            uart_putc(NAK);
            continue;
        }

        retries = 0;
        for (int i = 0; i < XMODEM_BLOCK_SIZE; i++)
            dest[total + i] = buf[i];
        total += XMODEM_BLOCK_SIZE;
        blk_num++;
        uart_putc(ACK);
    }
}

int main(void)
{
    neorv32_uart0_setup(UART_BAUD, 0);

    uart_puts("\r\n[stage2] ready - RV32IMAC NEORV32 U-Boot loader\r\n");
    uart_puts("[stage2] CLK="); uart_puthex32(neorv32_sysinfo_get_clk());
    uart_puts("\r\n");

    /* Verify SDRAM works before xmodem */
    if (!sdram_test()) {
        uart_puts("[stage2] SDRAM FAIL - halting\r\n");
        while (1) {}
    }

    uart_puts("[stage2] send U-Boot via xmodem at 115200 baud\r\n");

    uint8_t *dest = (uint8_t *)UBOOT_LOAD_ADDR;
    uint32_t size = xmodem_receive(dest);

    if (size == 0) {
        uart_puts("[stage2] xmodem FAILED\r\n");
        while (1) {}
    }

    /* Verify received binary — dump first 16 words */
    volatile uint32_t *p = (volatile uint32_t *)UBOOT_LOAD_ADDR;
    for (int i = 0; i < 16; i++) {
        if (i % 4 == 0) {
            uart_puts("\r\n  ");
            uart_puthex32(UBOOT_LOAD_ADDR + i * 4);
            uart_puts(": ");
        }
        uart_puthex32(p[i]);
        uart_putc(' ');
    }
    uart_puts("\r\n");

    uart_puts("[stage2] jumping to SDRAM 0x40000000...\r\n");

    __asm__ volatile ("fence.i" ::: "memory");

    void (*uboot)(void) = (void (*)(void))UBOOT_LOAD_ADDR;
    uboot();

    return 0;
}
