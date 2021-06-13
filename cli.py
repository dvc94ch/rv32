import argparse
import os
from nmigen import Fragment
from nmigen.back import verilog
from nmigen.sim import *
from nmigen_boards.ice40_hx8k_b_evn import *
from rv32.core import RV32, Top, read_prog


def compile_prog(path):
    os.system("mkdir -p build")
    os.system("riscv32-elf-as %s -o build/bin.o" % path)
    os.system("riscv32-elf-ld build/bin.o -o build/bin.ld.o -T progs/rv32.ld")
    os.system("riscv32-elf-objcopy build/bin.ld.o build/bin -j .text -O binary")
    os.system("riscv32-elf-objdump -d build/bin.ld.o -M no-aliases,numeric")


def build_fpga(path):
    compile_prog(path)
    prog = read_prog('build/bin')
    platform = ICE40HX8KBEVNPlatform()
    platform.build(Top(prog))


def flash():
    os.system("iceprog build/top.bin")


def riscv_formal(path):
    cpu = RV32(reset_address = 0x0000_0000, with_rvfi=True)
    ports = [
        cpu.ibus.ack,
        cpu.ibus.adr,
        cpu.ibus.bte,
        cpu.ibus.cti,
        cpu.ibus.cyc,
        cpu.ibus.dat_r,
        cpu.ibus.dat_w,
        cpu.ibus.sel,
        cpu.ibus.stb,
        cpu.ibus.we,
        cpu.ibus.err,

        cpu.dbus.ack,
        cpu.dbus.adr,
        cpu.dbus.bte,
        cpu.dbus.cti,
        cpu.dbus.cyc,
        cpu.dbus.dat_r,
        cpu.dbus.dat_w,
        cpu.dbus.sel,
        cpu.dbus.stb,
        cpu.dbus.we,
        cpu.dbus.err,

        cpu.rvfi.valid,
        cpu.rvfi.order,
        cpu.rvfi.insn,
        cpu.rvfi.trap,
        cpu.rvfi.halt,
        cpu.rvfi.intr,
        cpu.rvfi.mode,
        cpu.rvfi.ixl,
        cpu.rvfi.rs1_addr,
        cpu.rvfi.rs2_addr,
        cpu.rvfi.rs1_rdata,
        cpu.rvfi.rs2_rdata,
        cpu.rvfi.rd_addr,
        cpu.rvfi.rd_wdata,
        cpu.rvfi.pc_rdata,
        cpu.rvfi.pc_wdata,
        cpu.rvfi.mem_addr,
        cpu.rvfi.mem_rmask,
        cpu.rvfi.mem_wmask,
        cpu.rvfi.mem_rdata,
        cpu.rvfi.mem_wdata,
    ]

    fragment = Fragment.get(cpu, None)
    output = verilog.convert(fragment, name="rv32_cpu", ports=ports)
    with open('formal/rv32.v', 'w') as f:
        f.write(output)

    os.chdir("formal")
    os.system("rm -rf checks")
    os.system("python3 ../%s/checks/genchecks.py" % path)
    os.system("make -C checks -j$(nproc)")


def run_tests():
    os.system("mkdir -p vcd")
    os.system("python3 -m rv32.alu")
    os.system("python3 -m rv32.branch")
    os.system("python3 -m rv32.core")
    os.system("python3 -m rv32.decoder")
    os.system("python3 -m rv32.loadstore")
    os.system("python3 -m rv32.ram")
    os.system("python3 -m rv32.regs")
    os.system("python3 -m rv32.rom")


def main():
    parser = argparse.ArgumentParser()


    p_action = parser.add_subparsers(dest = "action")

    p_fpga = p_action.add_parser("fpga", help="build for fpga")
    p_fpga.add_argument("--bin", help="binary to load")

    p_formal = p_action.add_parser("formal", help="run formal verification")
    p_formal.add_argument("--riscv-formal-dir", help="path to riscv-formal dir")

    p_sim = p_action.add_parser("test", help="run tests")

    p_flash = p_action.add_parser("flash", help="flash program onto fpga")

    args = parser.parse_args()

    if args.action == 'fpga':
        build_fpga(args.bin)
    if args.action == 'formal':
        riscv_formal(args.riscv_formal_dir)
    if args.action == 'test':
        run_tests()
    if args.action == 'flash':
        flash()


if __name__ == '__main__':
    main()
