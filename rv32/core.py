from nmigen import *
from nmigen.hdl.rec import *
from nmigen.sim import *
from .alu import ALU
from .decoder import Decoder
from .regs import Registers
from .rom import ROM

wishbone_layout = [
    ("adr",   30, DIR_FANOUT),
    ("dat_w", 32, DIR_FANOUT),
    ("dat_r", 32, DIR_FANIN),
    ("sel",    4, DIR_FANOUT),
    ("cyc",    1, DIR_FANOUT),
    ("stb",    1, DIR_FANOUT),
    ("ack",    1, DIR_FANIN),
    ("we",     1, DIR_FANOUT),
    ("cti",    3, DIR_FANOUT),
    ("bte",    2, DIR_FANOUT),
    ("err",    1, DIR_FANIN)
]

# RISC-V Formal Interface
# https://github.com/SymbioticEDA/riscv-formal/blob/master/docs/rvfi.md

rvfi_layout = [
    ("valid",      1, DIR_FANOUT),
    ("order",     64, DIR_FANOUT),
    ("insn",      32, DIR_FANOUT),
    ("trap",       1, DIR_FANOUT),
    ("halt",       1, DIR_FANOUT),
    ("intr",       1, DIR_FANOUT),
    ("mode",       2, DIR_FANOUT),
    ("ixl",        2, DIR_FANOUT),

    ("rs1_addr",   5, DIR_FANOUT),
    ("rs2_addr",   5, DIR_FANOUT),
    ("rs1_rdata", 32, DIR_FANOUT),
    ("rs2_rdata", 32, DIR_FANOUT),
    ("rd_addr",    5, DIR_FANOUT),
    ("rd_wdata",  32, DIR_FANOUT),

    ("pc_rdata",  32, DIR_FANOUT),
    ("pc_wdata",  32, DIR_FANOUT),

    ("mem_addr",  32, DIR_FANOUT),
    ("mem_rmask",  4, DIR_FANOUT),
    ("mem_wmask",  4, DIR_FANOUT),
    ("mem_rdata", 32, DIR_FANOUT),
    ("mem_wdata", 32, DIR_FANOUT)
]

class RV32(Elaboratable):
    def __init__(self, reset_address=0x0000_0000, with_rvfi=False):
        self.reset_address = reset_address
        self.with_rvfi = with_rvfi

        self.ibus = Record(wishbone_layout)
        self.dbus = Record(wishbone_layout)
        if with_rvfi:
            self.rvfi = Record(rvfi_layout)

    def elaborate(self, platform):
        m = Module()

        pc = Signal(32, reset=self.reset_address)
        next_pc = Signal(32)
        trap = Signal()
        intr = Signal()
        funct4 = Signal(4)
        imm = Signal(32)
        imm_en = Signal()

        decoder = m.submodules.decoder = Decoder()
        regs    = m.submodules.regs    = Registers()
        alu     = m.submodules.alu     = ALU()

        m.d.comb += [
            self.ibus.adr.eq(pc[2:]),
            self.ibus.cyc.eq(1),
            self.ibus.stb.eq(1),
            decoder.inst.eq(self.ibus.dat_r),
            regs.rs1_addr.eq(decoder.rs1),
            regs.rs2_addr.eq(decoder.rs2),
            alu.funct4.eq(funct4),
            alu.in1.eq(regs.rs1_data),
            alu.in2.eq(Mux(imm_en, imm, regs.rs2_data)),
            regs.rd_data.eq(alu.out),
        ]
        m.d.sync += [
            funct4.eq(decoder.funct4),
            imm.eq(decoder.imm),
            imm_en.eq(decoder.imm_en),
            regs.rd_addr.eq(decoder.rd),
        ]

        m.d.comb += [
            self.rvfi.halt.eq(0),
            self.rvfi.mode.eq(Const(3)), # M-mode
            self.rvfi.ixl.eq(Const(1)), # XLEN=32
            # Memory Access
            self.rvfi.mem_addr.eq(0),
            self.rvfi.mem_wmask.eq(0),
            self.rvfi.mem_rmask.eq(0),
            self.rvfi.mem_rdata.eq(0),
            self.rvfi.mem_wdata.eq(0),
        ]

        with m.FSM():
            with m.State('FETCH'):
                m.d.comb += self.ibus.cyc.eq(1)
                with m.If(self.ibus.ack):
                    m.next = 'EXECUTE'
                    with m.If(decoder.trap):
                        m.d.comb += next_pc.eq(pc)
                        m.d.comb += trap.eq(1)
                    with m.Else():
                        m.d.comb += next_pc.eq(pc + 4)
                        m.d.comb += trap.eq(0)

                    m.d.sync += [
                        self.rvfi.pc_rdata.eq(pc),
                        self.rvfi.pc_wdata.eq(next_pc),
                        self.rvfi.insn.eq(self.ibus.dat_r),
                        self.rvfi.rs1_addr.eq(decoder.rs1),
                        self.rvfi.rs2_addr.eq(decoder.rs2),
                        self.rvfi.rd_addr.eq(decoder.rd),
                        self.rvfi.trap.eq(trap),
                        intr.eq(trap | intr),
                        pc.eq(next_pc),
                    ]
            with m.State('EXECUTE'):
                m.next = 'FETCH'
                m.d.comb += [
                    self.rvfi.valid.eq(~self.rvfi.trap),
                    regs.rd_we.eq(self.rvfi.valid),
                    self.rvfi.intr.eq(self.rvfi.valid & intr),
                    self.rvfi.rs1_rdata.eq(regs.rs1_data),
                    self.rvfi.rs2_rdata.eq(regs.rs2_data),
                    self.rvfi.rd_wdata.eq(Mux(self.rvfi.rd_addr, regs.rd_data, 0)),
                ]
                with m.If(self.rvfi.valid):
                    m.d.sync += self.rvfi.order.eq(self.rvfi.order + 1)
                    m.d.sync += intr.eq(0)
                m.d.sync += self.rvfi.trap.eq(0)

        return m


class Top(Elaboratable):
    def __init__(self, prog):
        self.cpu = RV32(with_rvfi=True)
        self.rvfi = self.cpu.rvfi
        self.rom = ROM(prog)
        self.clk = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.cpu = self.cpu
        m.submodules.rom = self.rom

        cd_por = ClockDomain(reset_less=True)
        m.domains += cd_por
        delay = Signal(1, reset = 1)
        with m.If(delay != 0):
            m.d.por += delay.eq(delay - 1)

        m.d.comb += [
            ClockSignal().eq(cd_por.clk),
            ResetSignal().eq(delay != 0),
            self.rom.cyc.eq(self.cpu.ibus.cyc),
            self.rom.stb.eq(self.cpu.ibus.stb),
            self.rom.adr.eq(self.cpu.ibus.adr),
            self.cpu.ibus.ack.eq(self.rom.ack),
            self.cpu.ibus.dat_r.eq(self.rom.dat_r),
        ]
        return m

if __name__ == '__main__':
    prog = [
        0b000000000001_00000_000_00001_0010011, # addi x1, x0, 1
        0b000000000001_00001_000_00001_0010011, # addi x1, x1, 1
        0b000000000001_00001_000_00001_0010011, # addi x1, x1, 1
        0x00000000,
    ]
    dut = Top(prog)
    sim = Simulator(dut)
    with sim.write_vcd('rv32.vcd'):
        def proc():
            yield Tick()
            yield Tick()
            yield Settle()
            assert(yield dut.rvfi.valid == 1)
            assert(yield dut.rvfi.pc_rdata == 0)
            assert(yield dut.rvfi.pc_wdata == 4)
            assert(yield dut.rvfi.insn == prog[0])
            assert(yield dut.rvfi.rs1_addr == 0)
            assert(yield dut.rvfi.rs1_rdata == 0)
            assert(yield dut.rvfi.rd_addr == 1)
            assert(yield dut.rvfi.rd_wdata == 1)

            yield Tick()
            yield Tick()
            yield Settle()
            assert(yield dut.rvfi.valid == 1)
            assert(yield dut.rvfi.pc_rdata == 4)
            assert(yield dut.rvfi.pc_wdata == 8)
            assert(yield dut.rvfi.insn == prog[1])
            assert(yield dut.rvfi.rs1_addr == 1)
            assert(yield dut.rvfi.rs1_rdata == 1)
            assert(yield dut.rvfi.rd_addr == 1)
            assert(yield dut.rvfi.rd_wdata == 2)

            yield Tick()
            yield Tick()
            yield Settle()
            assert(yield dut.rvfi.valid == 1)
            assert(yield dut.rvfi.pc_rdata == 8)
            assert(yield dut.rvfi.pc_wdata == 12)
            assert(yield dut.rvfi.insn == prog[2])
            assert(yield dut.rvfi.rs1_addr == 1)
            assert(yield dut.rvfi.rs1_rdata == 2)
            assert(yield dut.rvfi.rd_addr == 1)
            assert(yield dut.rvfi.rd_wdata == 3)

            yield Tick()
            yield Tick()
            yield Tick()
            yield Tick()
            yield Settle()

        sim.add_clock(1e-6, domain='por')
        sim.add_sync_process(proc)
        sim.run()
