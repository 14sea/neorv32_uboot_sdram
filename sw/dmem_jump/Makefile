# dmem_jump/Makefile — DMEM execution test for NEORV32 on AX301

MARCH = rv32imc_zicsr_zifencei

RISCV_PREFIX = /home/test/xpack-riscv-none-elf-gcc-14.2.0-3/bin/riscv-none-elf-

EFFORT = -Os

# Must match current RTL: IMEM=8KB, DMEM=8KB
USER_FLAGS += -Wl,--defsym,__neorv32_rom_size=8k
USER_FLAGS += -Wl,--defsym,__neorv32_ram_size=8k

UART_TTY ?= /dev/ttyUSB0

NEORV32_HOME ?= ../../neorv32

include $(NEORV32_HOME)/sw/common/common.mk
