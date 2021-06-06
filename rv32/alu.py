from nmigen import *
from nmigen.sim import *


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
        self.in1 = Signal(signed(32))
        self.in2 = Signal(signed(32))
        self.out = Signal(signed(32))

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
                m.d.comb += self.out.eq(self.in1 < self.in2)
            with m.Case(Funct4.SLTU):
                m.d.comb += self.out.eq(Cat(0, self.in1) < Cat(0, self.in2))
            with m.Case(Funct4.XOR):
                m.d.comb += self.out.eq(self.in1 ^ self.in2)
            with m.Case(Funct4.SRL):
                m.d.comb += self.out.eq(Cat(0, self.in1) >> (self.in2[:5] + 1))
            with m.Case(Funct4.SRA):
                m.d.comb += self.out.eq(self.in1 >> self.in2[:5])
            with m.Case(Funct4.OR):
                m.d.comb += self.out.eq(self.in1 | self.in2)
            with m.Case(Funct4.AND):
                m.d.comb += self.out.eq(self.in1 & self.in2)

        return m


def test_alu(funct4, in1, in2, expected):
    dut = ALU()
    sim = Simulator(dut)

    with sim.write_vcd('alu.vcd'):
        def proc():
            yield dut.funct4.eq(funct4)
            yield dut.in1.eq(in1)
            yield dut.in2.eq(in2)
            yield Settle()
            out = yield dut.out
            if out != expected:
                raise ValueError('expected %s but got %s' % (expected, out))

    sim.add_process(proc)
    sim.run()

if __name__ == '__main__':
    test_alu(Funct4.ADD, 3, 4, 7)
    test_alu(Funct4.SUB, 3, -4, 7)
    test_alu(Funct4.SLL, 0b1111, 4, 0b11110000)
    test_alu(Funct4.SLT, -1, 1, 1)
    test_alu(Funct4.SLTU, -1, 1, 0)
    test_alu(Funct4.XOR, 0b0011, 0b0101, 0b0110)
    test_alu(Funct4.SRL, -1, 4, 0x0fff_ffff)
    test_alu(Funct4.SRA, -1, 4, -1)
    test_alu(Funct4.OR, 0b0011, 0b0101, 0b0111)
    test_alu(Funct4.AND, 0b0011, 0b0101, 0b0001)
