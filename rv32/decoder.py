from nmigen import *
from nmigen.sim import *


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


class Decoder(Elaboratable):
    def __init__(self):
        self.inst = Signal(32)
        self.imm = Signal(32)
        self.imm_en = Signal()
        self.funct4 = Signal(4)
        self.rs1 = Signal(5)
        self.rs2 = Signal(5)
        self.rd = Signal(5)
        self.trap = Signal()

    def elaborate(self, platform):
        m = Module()
        inst = self.inst
        rd = inst[7:12]
        rs1 = inst[15:20]
        rs2 = inst[20:25]
        funct3 = inst[12:15]
        funct7 = inst[25:32]
        funct1_en = Signal()
        funct1_valid = Signal()
        funct1 = Mux(funct1_en, funct7[5], 0)

        m.d.comb += [
            self.imm_en.eq(1),
            self.rd.eq(rd),
            self.rs1.eq(rs1),
            self.rs2.eq(Mux(self.imm_en, 0, rs2)),
            self.funct4.eq(Cat(funct1, funct3)),
        ]
        with m.If(inst[0:2] != 0b11):
            m.d.comb += self.trap.eq(1)
        with m.Switch(funct7):
            with m.Case('0000000'):
                m.d.comb += funct1_valid.eq(1)
            with m.Case('0100000'):
                with m.If(funct3 == 0b101):
                    m.d.comb += funct1_valid.eq(1)
                with m.If(funct3 == 0b000):
                    m.d.comb += funct1_valid.eq(1)
        with m.If(funct1_en & ~funct1_valid):
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
                        m.d.comb += funct1_en.eq(1)
                        m.d.comb += self.imm.eq(inst[20:25])
            with m.Case(Opcode.REG):
                m.d.comb += self.imm_en.eq(0)
                m.d.comb += funct1_en.eq(1)
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
