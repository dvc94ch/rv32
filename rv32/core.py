from nmigen import *
from nmigen.hdl.rec import *
from nmigen.sim import *
from .alu import ALU
from .branch import Branch
from .decoder import Decoder, PcOp
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

        decoder = m.submodules.decoder = Decoder()
        regs    = m.submodules.regs    = Registers()
        alu     = m.submodules.alu     = ALU()
        branch  = m.submodules.branch  = Branch()

        pc = Signal(32, reset=self.reset_address)
        pc_next = Signal(32)
        pc_4 = Signal(32)
        inst = Signal(32)
        m.d.comb += pc_4.eq(pc + 4)
        rs1_en = Signal()
        rs2_en = Signal()
        trap = Signal()
        m.d.comb += [
            self.ibus.adr.eq(pc[2:]),
            self.ibus.cyc.eq(1),
            self.ibus.stb.eq(1),
            decoder.inst.eq(self.ibus.dat_r),
            regs.rs1_addr.eq(decoder.rs1),
            regs.rs2_addr.eq(decoder.rs2),
            regs.rd_addr.eq(decoder.rd),
            alu.funct4.eq(Cat(decoder.funct1, decoder.funct3)),
            alu.in1.eq(Mux(rs1_en, regs.rs1_data, pc)),
            alu.in2.eq(Mux(rs2_en, regs.rs2_data, decoder.imm)),
            branch.funct3.eq(decoder.funct3),
            branch.in1.eq(regs.rs1_data),
            branch.in2.eq(regs.rs2_data),
        ]

        with m.Switch(decoder.pc_op):
            with m.Case(PcOp.NEXT):
                m.d.comb += [
                    rs1_en.eq(decoder.rs1_en),
                    rs2_en.eq(decoder.rs2_en),
                    pc_next.eq(pc_4),
                    regs.rd_data.eq(alu.out),
                ]
            with m.Case(PcOp.JAL):
                m.d.comb += [
                    rs1_en.eq(0),
                    rs2_en.eq(0),
                    pc_next.eq(alu.out),
                    regs.rd_data.eq(pc_4),
                ]
            with m.Case(PcOp.JALR):
                m.d.comb += [
                    rs1_en.eq(1),
                    rs2_en.eq(0),
                    pc_next.eq(alu.out),
                    regs.rd_data.eq(pc_4),
                ]
            with m.Case(PcOp.BRANCH):
                m.d.comb += [
                    rs1_en.eq(0),
                    rs2_en.eq(0),
                    pc_next.eq(Mux(branch.out, alu.out, pc_4)),
                ]
        with m.If(decoder.trap):
            m.d.comb += pc_next.eq(pc)

        with m.FSM():
            with m.State('FETCH'):
                m.d.comb += self.ibus.cyc.eq(1)
                with m.If(self.ibus.ack):
                    m.next = 'EXECUTE'
                    m.d.sync += inst.eq(self.ibus.dat_r)
                    m.d.comb += decoder.inst.eq(self.ibus.dat_r)
            with m.State('EXECUTE'):
                m.next = 'WRITE'
                m.d.comb += decoder.inst.eq(inst)
                m.d.comb += trap.eq(decoder.trap | pc_next[0] | pc_next[1])
                m.d.comb += regs.rd_we.eq(~trap & decoder.rd_en)
                m.d.comb += self.rvfi.valid.eq(~trap)
                m.d.comb += self.rvfi.trap.eq(trap)
                m.d.sync += pc.eq(pc_next)
            with m.State('WRITE'):
                m.next = 'FETCH'

        m.d.comb += [
            self.rvfi.halt.eq(0),
            self.rvfi.mode.eq(Const(3)), # M-mode
            self.rvfi.ixl.eq(Const(1)), # XLEN=32
            self.rvfi.intr.eq(0),

            self.rvfi.pc_rdata.eq(pc),
            self.rvfi.pc_wdata.eq(pc_next),
            self.rvfi.insn.eq(inst),
            self.rvfi.rs1_addr.eq(decoder.rs1),
            self.rvfi.rs1_rdata.eq(regs.rs1_data),
            self.rvfi.rs2_addr.eq(decoder.rs2),
            self.rvfi.rs2_rdata.eq(regs.rs2_data),
            self.rvfi.rd_addr.eq(decoder.rd),
            self.rvfi.rd_wdata.eq(Mux(decoder.rd_en & (regs.rd_addr != 0), regs.rd_data, 0)),
            self.rvfi.trap.eq(trap),

            # Memory Access
            self.rvfi.mem_addr.eq(0),
            self.rvfi.mem_wmask.eq(0),
            self.rvfi.mem_rmask.eq(0),
            self.rvfi.mem_rdata.eq(0),
            self.rvfi.mem_wdata.eq(0),
        ]
        with m.If(self.rvfi.valid):
            m.d.sync += self.rvfi.order.eq(self.rvfi.order + 1)

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
    assert_en = False
    with sim.write_vcd('rv32.vcd'):
        def step():
            yield Tick()
            yield Settle()
            while (yield dut.rvfi.valid) != 1:
                yield Tick()
                yield Settle()

        def proc():
            clock = 0
            yield from step()
            if assert_en:
                assert(yield dut.rvfi.pc_rdata == 0)
                assert(yield dut.rvfi.pc_wdata == 4)
                assert(yield dut.rvfi.insn == prog[0])
                assert(yield dut.rvfi.rs1_addr == 0)
                assert(yield dut.rvfi.rs1_rdata == 0)
                assert(yield dut.rvfi.rd_addr == 1)
                assert(yield dut.rvfi.rd_wdata == 1)

            yield from step()
            if assert_en:
                assert(yield dut.rvfi.pc_rdata == 4)
                assert(yield dut.rvfi.pc_wdata == 8)
                assert(yield dut.rvfi.insn == prog[1])
                assert(yield dut.rvfi.rs1_addr == 1)
                assert(yield dut.rvfi.rs1_rdata == 1)
                assert(yield dut.rvfi.rd_addr == 1)
                assert(yield dut.rvfi.rd_wdata == 2)

            yield from step()
            if assert_en:
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
