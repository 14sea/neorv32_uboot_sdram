// hello_world/main.c — NEORV32 Hello World for AX301 (EP4CE6F17C8)
//
// Prints "Hello from NEORV32!" over UART0 at 115200 baud,
// then blinks LEDs (gpio_o[3:0]) in a walking-LED pattern.
//
// Boot sequence:
//   1. FPGA programmed with neorv32_demo bitstream
//   2. NEORV32 bootloader starts (19200 baud), prints menu
//   3. Host sends this app via: make upload UART_TTY=/dev/ttyUSB0
//   4. Bootloader jumps to 0x00000000; app sets UART to 115200
//   5. Open /dev/ttyUSB0 at 115200 to see output

#include <neorv32.h>

#define BAUD_RATE 115200

int main(void) {

    // Setup NEORV32 runtime environment (trap handler, etc.)
    neorv32_rte_setup();

    // Setup UART0 at 115200 baud, no RX/TX interrupts
    neorv32_uart0_setup(BAUD_RATE, 0);

    // Banner
    neorv32_uart0_printf("\n\n");
    neorv32_uart0_printf("=================================\n");
    neorv32_uart0_printf("  Hello from NEORV32 on AX301!  \n");
    neorv32_uart0_printf("=================================\n");
    neorv32_uart0_printf("  CPU: RV32IMC  Clock: 50 MHz   \n");
    neorv32_uart0_printf("  IMEM: 16 KB   DMEM: 8 KB      \n");
    neorv32_uart0_printf("  SDRAM: 32 MB (Wishbone XBUS)  \n");
    neorv32_uart0_printf("=================================\n\n");

    // Print MHARTID (should be 0)
    neorv32_uart0_printf("mhartid  = 0x%x\n", neorv32_cpu_csr_read(CSR_MHARTID));
    neorv32_uart0_printf("clock    = %u Hz\n", NEORV32_SYSINFO->CLK);
    uint32_t misc = NEORV32_SYSINFO->MISC;
    neorv32_uart0_printf("IMEM     = %u bytes\n", 1u << ((misc >> 0) & 0xFF));
    neorv32_uart0_printf("DMEM     = %u bytes\n", 1u << ((misc >> 8) & 0xFF));

    neorv32_uart0_printf("\nStarting LED blink loop...\n");

    // Walking LED pattern on gpio_o[3:0]
    // LEDs are active-low on AX301, but gpio drives them via NOT in VHDL wrapper
    // so gpio_o=1 → LED on
    uint32_t led = 1;
    uint32_t cnt = 0;

    while (1) {
        neorv32_gpio_port_set(led);

        // Simple delay (~500 ms at 50 MHz, with RV32IMC instruction overhead)
        for (volatile uint32_t d = 0; d < 2500000; d++) { }

        led = (led << 1);
        if (led > 0x8) led = 0x1;

        // Print counter every 4 steps (once per full cycle)
        cnt++;
        if ((cnt & 3) == 0) {
            neorv32_uart0_printf("tick %u\n", cnt >> 2);
        }
    }

    return 0;
}
