# NEORV32 + SDRAM U-Boot Boot Flow (AX301 / Cyclone IV)

Runs NEORV32 on AX301 and boots U-Boot from external SDRAM via a two-stage loader.

## Hardware Target

- Board: Heijin AX301
- FPGA: Altera Cyclone IV EP4CE6F17C8
- External memory: 32 MB SDRAM

## Project Layout

- `rtl/`: SoC integration + SDRAM controller glue
- `quartus/`: Quartus project files
- `host/`: host tools for boot/upload (`boot_uboot.py`)
- `sw/`: software payloads (`stage2_loader`, demos)
- `neorv32/`: vendored NEORV32 source tree

## Prerequisites

- Quartus Prime Lite
- RISC-V GCC toolchain (`riscv-none-elf-*`)
- Python 3 + `pyserial`
- `openFPGALoader`
- U-Boot binary (`u-boot.bin`) built separately

## Build

```bash
# Build stage2 loader
cd sw/stage2_loader
make

# Build FPGA image
cd ../../quartus
quartus_sh --flow compile neorv32_demo
quartus_cpf -c -o bitstream_compression=off neorv32_demo.sof ../neorv32_demo.rbf
```

## Boot U-Boot

```bash
cd ..
python3 host/boot_uboot.py --port /dev/ttyUSB0 --uboot ~/u-boot/u-boot.bin
```

Then connect terminal:

```bash
minicom -b 115200 -D /dev/ttyUSB0
```

## Boot Sequence Summary

1. NEORV32 ROM bootloader receives `stage2_loader`
2. Stage2 switches to 115200 and requests XMODEM transfer
3. Host sends `u-boot.bin` into SDRAM at `0x40000000`
4. Stage2 jumps to SDRAM and enters U-Boot

## Notes

- This repo intentionally excludes generated `.rbf/.sof` and build outputs.
## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
The `neorv32/` submodule remains under its original BSD 3-Clause License.
