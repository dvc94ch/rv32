from nmigen import *
from nmigen.sim import *


class Opcode:
    LUI    = 0b0110111
    AUIPC  = 0b0010111
    JAL    = 0b1101111
    JALR   = 0b1100111
    BRANCH = 0b1100011
    LOAD   = 0b0000011
    STORE  = 0b0100011
    IMM    = 0b0010011
    REG    = 0b0110011

class PcOp:
    NEXT   = 0b00
    JAL    = 0b01
    JALR   = 0b10
    BRANCH = 0b11

class Decoder(Elaboratable):
    def __init__(self):
        self.inst = Signal(32)

        self.rs1 = Signal(5)
        self.rs1_en = Signal()

        self.rs2 = Signal(5)
        self.rs2_en = Signal()

        self.rd = Signal(5)
        self.rd_en = Signal()

        self.pc_op = Signal(2)
        self.funct4 = Signal(4)

        self.imm = Signal(32)

        self.trap = Signal()

    def elaborate(self, platform):
        m = Module()
        inst = self.inst
        opcode = inst[:7]
        rd = inst[7:12]
        rs1 = inst[15:20]
        rs2 = inst[20:25]
        funct3 = inst[12:15]
        funct7 = inst[25:32]

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

        funct1 = Signal()
        funct1_valid = Signal()
        m.d.comb += [
            self.pc_op.eq(PcOp.NEXT),
            self.rs1.eq(Mux(self.rs1_en, rs1, 0)),
            self.rs2.eq(Mux(self.rs2_en, rs2, 0)),
            self.rd.eq(Mux(self.rd_en, rd, 0)),
            self.funct4.eq(Cat(funct1, funct3)),
        ]

        with m.Switch(funct7):
            with m.Case('0100000'):
                m.d.comb += [
                    funct1.eq(1),
                    funct1_valid.eq(1),
                ]
            with m.Case('0000000'):
                m.d.comb += [
                    funct1.eq(0),
                    funct1_valid.eq(1),
                ]
            with m.Default():
                m.d.comb += [
                    funct1.eq(0),
                    funct1_valid.eq(0),
                ]

        with m.Switch(opcode):
            with m.Case(Opcode.LUI):
                m.d.comb += [
                    self.rs1_en.eq(0),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                    self.imm.eq(imm_u),
            ]
            with m.Case(Opcode.AUIPC):
                m.d.comb += [
                    self.rs1_en.eq(0),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                    self.imm.eq(imm_u),
                ]
            with m.Case(Opcode.JAL):
                m.d.comb += [
                    self.rs1_en.eq(0),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                    self.pc_op.eq(PcOp.JAL),
                    self.imm.eq(imm_j),
                ]
            with m.Case(Opcode.JALR):
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                    self.pc_op.eq(PcOp.JALR),
                    self.imm.eq(imm_i),
                ]
            with m.Case(Opcode.BRANCH):
                with m.Switch(funct3):
                    with m.Case('01-'):
                        m.d.comb += self.trap.eq(1)
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(1),
                    self.rd_en.eq(0),
                    self.pc_op.eq(PcOp.BRANCH),
                    self.imm.eq(imm_b),
                ]
            with m.Case(Opcode.LOAD):
                with m.Switch(funct3):
                    with m.Case('11-'):
                        m.d.comb += self.trap.eq(1)
                    with m.Case('011'):
                        m.d.comb += self.trap.eq(1)
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                    self.imm.eq(imm_i),
                ]
            with m.Case(Opcode.STORE):
                with m.Switch(funct3):
                    with m.Case('1--'):
                        m.d.comb += self.trap.eq(1)
                    with m.Case('011'):
                        m.d.comb += self.trap.eq(1)
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(1),
                    self.rd_en.eq(0),
                    self.imm.eq(imm_s),
                ]
            with m.Case(Opcode.IMM):
                with m.Switch(Cat(funct3, funct1_valid)):
                    with m.Case('-011'):
                        m.d.comb += self.imm.eq(inst[20:25])
                    with m.Case('-010'):
                        m.d.comb += self.trap.eq(1)
                    with m.Default():
                        m.d.comb += self.imm.eq(imm_i)
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(0),
                    self.rd_en.eq(1),
                ]
            with m.Case(Opcode.REG):
                with m.If(~funct1_valid):
                    m.d.comb += self.trap.eq(1)
                m.d.comb += [
                    self.rs1_en.eq(1),
                    self.rs2_en.eq(1),
                    self.rd_en.eq(1),
                    self.imm.eq(0),
                ]
            with m.Default():
                m.d.comb += self.trap.eq(1)

        return m


def test_decoder(inst, funct4):
    dut = Decoder()
    sim = Simulator(dut)

    with sim.write_vcd('decoder.vcd'):
        def proc():
            yield dut.inst.eq(inst)
            yield Settle()
            assert(yield ~dut.trap)
            out = yield dut.funct4
            if out != funct4:
                raise ValueError('expected %s but got %s' % (funct4, out))

    sim.add_process(proc)
    sim.run()

if __name__ == '__main__':
    from .alu import Funct4
    inst = 0b000000000001_00000_000_00001_0010011 # addi x1, x0, 1
    test_decoder(inst, Funct4.ADD)
    print('ok')
    inst = 0b000000000000_00000_111_00001_0110011 # and x1, x0, x0
    test_decoder(inst, Funct4.AND)
    print('ok')
