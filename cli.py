import argparse
from nmigen import cli
from rv32.core import RV32

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--reset-address",
        type=lambda s: int(s, 16), default="0x00000000",
        help="reset vector address")

    parser.add_argument("--with-rvfi",
        default=False, action="store_true",
        help="enable the riscv-formal interface")

    cli.main_parser(parser)

    args = parser.parse_args()

    cpu = RV32(args.reset_address, args.with_rvfi)

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
    ]

    if args.with_rvfi:
        ports += [
            cpu.rvfi.valid, cpu.rvfi.order, cpu.rvfi.insn, cpu.rvfi.trap, cpu.rvfi.halt,
            cpu.rvfi.intr, cpu.rvfi.mode, cpu.rvfi.ixl, cpu.rvfi.rs1_addr, cpu.rvfi.rs2_addr,
            cpu.rvfi.rs1_rdata, cpu.rvfi.rs2_rdata, cpu.rvfi.rd_addr, cpu.rvfi.rd_wdata,
            cpu.rvfi.pc_rdata, cpu.rvfi.pc_wdata, cpu.rvfi.mem_addr, cpu.rvfi.mem_rmask,
            cpu.rvfi.mem_wmask, cpu.rvfi.mem_rdata, cpu.rvfi.mem_wdata,
        ]

    cli.main_runner(parser, args, cpu, name="rv32_cpu", ports=ports)


if __name__ == '__main__':
    main()
