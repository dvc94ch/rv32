#!/bin/sh

RISCV_FORMAL=../../riscv-formal
rm -rf checks
python3 ../cli.py --with-rvfi generate --type v > rv32.v
python3 $RISCV_FORMAL/checks/genchecks.py
make -C checks -j$(nproc)
