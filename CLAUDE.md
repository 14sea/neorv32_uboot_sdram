# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

NEORV32 RV32IMC soft-core running U-Boot from 32 MB SDRAM on a 黑金 AX301 (EP4CE6F17C8) FPGA. The working bitstream (`neorv32_demo.rbf`) has all known RTL bugs fixed. See the parent `CLAUDE.md` (`/home/test/fpga/CLAUDE.md`) for the board/toolchain setup.

## Commands

### Build bitstream (Quartus)
```bash
cd quartus
export PATH=$PATH:$HOME/intelFPGA_lite/21.1/quartus/bin
quartus_sh --flow compile neorv32_demo
quartus_cpf -c -o bitstream_compression=off neorv32_demo.sof ../neorv32_demo.rbf
```

### Program FPGA
```bash
../../openFPGALoader/build/openFPGALoader -c usb-blaster neorv32_demo.rbf
```

### Build firmware (hello_world or stage2_loader)
```bash
cd sw/hello_world   # or sw/stage2_loader
make exe            # → neorv32_exe.bin (NEORV32 bootloader upload format)
```
Toolchain: `/home/test/xpack-riscv-none-elf-gcc-14.2.0-3/bin/riscv-none-elf-`; set in each Makefile directly (no PATH needed).

### Build SDRAM test payloads (bare-metal asm, run from SDRAM)
```bash
cd sw/sdram_hello
riscv-none-elf-as -march=rv32imc -o diag_test.o diag_test.S
riscv-none-elf-ld -T link.ld -o diag_test.elf diag_test.o
riscv-none-elf-objcopy -O binary diag_test.elf diag_test.bin
```

### Full U-Boot boot sequence
```bash
cd /home/test/fpga/neorv32_demo
../../.env/bin/python host/boot_uboot.py --port /dev/ttyUSB0
# Options: --skip-program (skip FPGA programming), --rbf <path>, --uboot <path>
```

### Upload hello_world / small firmware via bootloader
```bash
../../.env/bin/python host/upload.py --port /dev/ttyUSB0 \
    --exe sw/hello_world/neorv32_exe.bin
```

### Send xmodem payload to stage2
```bash
../../.env/bin/python host/test_sdram_xmodem.py
# Edit PAYLOAD path in script; default is sdram_xmodem_test.bin
```

### Interactive U-Boot terminal
```bash
minicom -b 115200 -D /dev/ttyUSB0
```

## Architecture

### RTL (`rtl/`)
- **`ax301_top.vhd`** — Top-level VHDL wrapper. Instantiates NEORV32, connects UART/GPIO/SDRAM. Key generics: `IMEM_SIZE=8KB`, `ICACHE_EN=true`, `CACHE_BLOCK_SIZE=64`, `CACHE_BURSTS_EN=false`, `XBUS_EN=true`.
- **`wb_sdram_ctrl.v`** — Wishbone (XBUS) to `sdram_ctrl` bridge. Decodes `0x40000000–0x41FFFFFF`. Drives `pending`/`sel` into sdram_ctrl; manages read data latch and ACK timing.
- **`sdram_ctrl.v`** — SDRAM FSM for HY57V2562GTR (4M×16×4 banks, 32 MB). Two consecutive 16-bit reads/writes per 32-bit CPU word. `sdram_clk = ~clk` (inverted for setup/hold). Two fixed bugs in current version:
  - CL wait = `CL-1` (not `CL-2`): data valid at rising N+4 because clock is inverted
  - `S_DONE_W` state (5'd27): 1-cycle gap after `ready=1` so `wb_sdram_ctrl` can clear `pending` before FSM returns to `S_IDLE`, preventing spurious read

### NEORV32 connection
NEORV32 XBUS (Wishbone-compatible) → `wb_sdram_ctrl` → `sdram_ctrl` → SDRAM pins. The ICACHE issues **non-burst** locked transfers (one STB per word, `lock=1` throughout). D-bus issues single unlocked transfers. `XBUS_REGSTAGE_EN=false` (no extra pipeline stage on the bus).

### Firmware (`sw/`)
| Directory | Description |
|-----------|-------------|
| `hello_world/` | Standard NEORV32 Hello World; runs from IMEM at 115200 baud |
| `stage2_loader/` | xmodem receiver; runs from IMEM, receives U-Boot to SDRAM `0x40000000`, jumps via `fence.i` |
| `sdram_hello/` | Bare-metal asm payloads linked to `0x40000000`; UART markers + LED blink for SDRAM testing |

### Host scripts (`host/`)
| Script | Purpose |
|--------|---------|
| `boot_uboot.py` | Full sequence: FPGA program → bootloader → stage2 → xmodem U-Boot → interactive |
| `upload.py` | Bootloader upload only (19200 baud), switches to 115200 after `e` |
| `test_sdram_xmodem.py` | Upload stage2 then xmodem a small test payload; watch for pass string |

### Boot sequence
```
FPGA power-on → NEORV32 bootloader (0xFFE00000, 19200 baud, CMD:> prompt)
  'u' → upload stage2_loader (neorv32_exe.bin, ~2 KB)
  'e' → execute; switch UART to 115200
stage2_loader (IMEM 0x00000000):
  sends NAK → host xmodem-sends U-Boot.bin (163 KB) → SDRAM 0x40000000
  prints hex dump of first 16 words → jumps to 0x40000000
U-Boot (SDRAM, 0x40000000): DRAM: 32 MiB → U-Boot> prompt
```

## U-Boot port (`/home/test/u-boot/`)

Key U-Boot config (`configs/neorv32_ax301_defconfig`):
- `CONFIG_TEXT_BASE=0x40000000`, `CONFIG_SKIP_RELOCATE=y` (no relocation needed; loaded directly to TEXT_BASE)
- `CONFIG_RISCV_ACLINT=y` with CLINT at `0xFFF40000` (MTIME at +0xBFF8, standard ACLINT layout matching NEORV32)
- Debug UART: `CONFIG_DEBUG_UART_NEORV32=y` at `0xFFF50000`

**Critical fix in `common/board_f.c`:** `jump_to_copy()` calls `board_init_r(gd->new_gd, gd->relocaddr)` directly when `GD_FLG_SKIP_RELOC` is set. Without this, RISC-V startup relies on `relocate_code()` to jump to `board_init_r()`; with SKIP_RELOCATE, `board_init_f()` would fall into `hang()` instead.

### Rebuild U-Boot
```bash
cd /home/test/u-boot
export PATH=$PATH:/home/test/xpack-riscv-none-elf-gcc-14.2.0-3/bin
make ARCH=riscv CROSS_COMPILE=riscv-none-elf- neorv32_ax301_defconfig
make ARCH=riscv CROSS_COMPILE=riscv-none-elf- -j$(nproc)
# Output: u-boot.bin (163 KB)
```

## Known constraints

- **IMEM=8KB**: stage2 must fit in 8 KB. `__neorv32_rom_size=8k` in its Makefile.
- **ICACHE required**: NEORV32's 32-bit I-bus can't fetch from the 16-bit SDRAM without it. `CACHE_BURSTS_EN=false` — sdram_ctrl does not support burst mode.
- **M9K usage at 83%**: IMEM (8 KB) + DMEM (8 KB) + Boot ROM + ICACHE tags leave almost no room. Do not add BRAMs.
- **sdram_clk = ~clk**: Any timing changes to sdram_ctrl must account for the inverted clock; the CPU sees CL=3 but capture happens at rising edge N+4 (not N+3).
- **Bootloader baud switching**: Bootloader uses 19200; after `e`, the app runs at 115200. Do not flush the serial buffer after switching — the banner/NAK arrives immediately.
