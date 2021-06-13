#!/bin/sh
BIN=$1
riscv32-elf-as ${BIN}.s -o ${BIN}.o
riscv32-elf-ld ${BIN}.o -T rv32.ld -o ${BIN}.ld.o
riscv32-elf-objcopy ${BIN}.ld.o -j .text -O binary ${BIN}.bin
riscv32-elf-objdump -d ${BIN}.ld.o -M no-aliases,numeric
