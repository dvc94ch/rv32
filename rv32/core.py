from nmigen import *
from nmigen.hdl.rec import *

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

        regfile = Memory(width = 31, depth = 32)
        decoder = m.submodules.decoder = Decoder()
        rs1     = m.submodules.rs1     = regfile.read_port()
        rs2     = m.submodules.rs2     = regfile.read_port()
        rd      = m.submodules.rd      = regfile.write_port()
        alu     = m.submodules.alu     = ALU()

        m.d.comb += [
            self.ibus.adr.eq(pc[2:]),
            self.ibus.cyc.eq(1),
            self.ibus.stb.eq(1),
            decoder.inst.eq(self.ibus.dat_r),
            rs1.addr.eq(~decoder.rs1),
            rs2.addr.eq(~decoder.rs2),
            rd.addr.eq(~decoder.rd),
            alu.funct4.eq(decoder.funct4),
            alu.in1.eq(rs1.data),
            rd.data.eq(alu.out),
        ]
        m.d.sync += [
            alu.in2.eq(Mux(decoder.shamt_or_reg, rs2.data, decoder.imm)),
        ]

        with m.FSM():
            with m.State('FETCH'):
                m.d.comb += self.ibus.cyc.eq(1)
                with m.If(self.ibus.ack == 1):
                    m.next = 'EXECUTE'
                    m.d.comb += [
                        next_pc.eq(Mux(decoder.trap, self.reset_address, pc + 4)),
                    ]
                    m.d.sync += [
                        self.rvfi.pc_rdata.eq(pc),
                        self.rvfi.pc_wdata.eq(next_pc),
                        self.rvfi.trap.eq(decoder.trap),
                        self.rvfi.insn.eq(self.ibus.dat_r),
                        self.rvfi.rs1_addr.eq(decoder.rs1),
                        self.rvfi.rs2_addr.eq(decoder.rs2),
                        self.rvfi.rd_addr.eq(decoder.rd),
                        pc.eq(next_pc),
                    ]
            with m.State('EXECUTE'):
                m.next = 'FETCH'
                m.d.comb += [
                    rd.en.eq(~self.rvfi.trap),
                    self.rvfi.valid.eq(~self.rvfi.trap),
                ]

        with m.If(self.rvfi.valid == 1):
            m.d.sync += [
                self.rvfi.order.eq(self.rvfi.order + 1),
            ]
        m.d.comb += [
            self.rvfi.halt.eq(0),
            self.rvfi.intr.eq(0),
            self.rvfi.mode.eq(Const(3)), # M-mode
            self.rvfi.ixl.eq(Const(1)), # XLEN=32
            # Integer Register Read/Write
            self.rvfi.rs1_rdata.eq(rs1.data),
            self.rvfi.rs2_rdata.eq(rs2.data),
            self.rvfi.rd_wdata.eq(rd.data),
            # Memory Access
            self.rvfi.mem_addr.eq(0),
            self.rvfi.mem_wmask.eq(0),
            self.rvfi.mem_rmask.eq(0),
            self.rvfi.mem_rdata.eq(0),
            self.rvfi.mem_wdata.eq(0),
        ]

        return m


class Decoder(Elaboratable):
    def __init__(self):
        self.inst = Signal(32)
        self.imm = Signal(32)
        self.rs1 = Signal(5)
        self.rs2 = Signal(5)
        self.rd = Signal(5)
        self.funct4 = Signal(4)
        self.shamt_or_reg = Signal()
        self.trap = Signal()

    def elaborate(self, platform):
        m = Module()
        inst = self.inst
        funct3 = inst[12:15]
        funct7 = inst[25:32]
        funct7_valid = Signal()
        m.d.comb += [
            self.rs1.eq(inst[15:20]),
            self.rs2.eq(Mux(self.shamt_or_reg, inst[20:25], 0)),
            self.rd.eq(inst[7:12]),
            self.funct4.eq(Cat(Mux(self.shamt_or_reg, funct7[5], 0), funct3)),
        ]
        with m.Switch(funct7):
            with m.Case('0-00000'):
                with m.If(funct3 == 0b101):
                    m.d.comb += funct7_valid.eq(1)
                with m.If(funct3 == 0b000):
                    m.d.comb += funct7_valid.eq(1)
        with m.If(inst[0:2] != 0b11):
            m.d.comb += self.trap.eq(1)
        with m.If(self.shamt_or_reg & ~funct7_valid):
            m.d.comb += self.trap.eq(1)

        imm_i = Signal(32)
        imm_s = Signal(32)
        imm_b = Signal(32)
        imm_u = Signal(32)
        imm_j = Signal(32)
        m.d.comb += [
            imm_i.eq(Cat(inst[20:31], Repl(inst[31], 21))),
            imm_s.eq(Cat(inst[7], inst[8:12], inst[25:31], Repl(inst[31], 21))),
            imm_b.eq(Cat(0, inst[8:12], inst[25:31], inst[7], Repl(inst[31], 20))),
            imm_u.eq(Cat(Repl(0, 12), inst[12:20], inst[20:31], inst[31])),
            imm_j.eq(Cat(0, inst[21:25], inst[25:31], inst[20], inst[12:19], Repl(inst[31], 12))),
        ]
        with m.Switch(inst[2:7]):
            '''with m.Case(Opcode.LUI):
                m.d.comb += self.imm.eq(imm_u)
            with m.Case(Opcode.AUIPC):
                m.d.comb += self.imm.eq(imm_u)
            with m.Case(Opcode.JAL):
                m.d.comb += self.imm.eq(imm_j)
            with m.Case(Opcode.JALR):
                m.d.comb += self.imm.eq(imm_i)
            with m.Case(Opcode.BRANCH):
                m.d.comb += self.imm.eq(imm_b)
            with m.Case(Opcode.LOAD):
                m.d.comb += self.imm.eq(imm_i)
            with m.Case(Opcode.STORE):
                m.d.comb += self.imm.eq(imm_s)'''
            with m.Case(Opcode.IMM):
                m.d.comb += self.imm.eq(imm_i)
                with m.Switch(funct3):
                    with m.Case('-01'):
                        m.d.comb += self.shamt_or_reg.eq(1)
            with m.Case(Opcode.REG):
                m.d.comb += self.shamt_or_reg.eq(1)
            with m.Default():
                m.d.comb += self.trap.eq(1)
        return m


class Opcode:
    LUI    = 0b01101
    AUIPC  = 0b00101
    JAL    = 0b11011
    JALR   = 0b11001
    BRANCH = 0b11000
    LOAD   = 0b00000
    STORE  = 0b01000
    IMM    = 0b00100
    REG    = 0b01100


class Funct4:
    ADD  = 0b0000
    SUB  = 0b0001
    SLL  = 0b0010
    SLT  = 0b0100
    SLTU = 0b0110
    XOR  = 0b1000
    SRL  = 0b1010
    SRA  = 0b1011
    OR   = 0b1100
    AND  = 0b1110


class ALU(Elaboratable):
    def __init__(self):
        self.funct4 = Signal(4)
        self.in1 = Signal(32)
        self.in2 = Signal(32)
        self.out = Signal(32)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct4):
            with m.Case(Funct4.ADD):
                m.d.comb += self.out.eq(self.in1 + self.in2)
            with m.Case(Funct4.SUB):
                m.d.comb += self.out.eq(self.in1 - self.in2)
            with m.Case(Funct4.SLL):
                m.d.comb += self.out.eq(self.in1 << self.in2[:5])
            with m.Case(Funct4.SLT):
                # TODO
                pass
            with m.Case(Funct4.SLTU):
                # TODO
                pass
            with m.Case(Funct4.XOR):
                m.d.comb += self.out.eq(self.in1 ^ self.in2)
            with m.Case(Funct4.SRL):
                m.d.comb += self.out.eq(self.in1 >> self.in2[:5])
            with m.Case(Funct4.SRA):
                # TODO
                pass
            with m.Case(Funct4.OR):
                m.d.comb += self.out.eq(self.in1 | self.in2)
            with m.Case(Funct4.AND):
                m.d.comb += self.out.eq(self.in1 & self.in2)
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
    from nmigen.sim import *
    from rom import ROM
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
