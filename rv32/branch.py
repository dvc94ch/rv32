from nmigen import *
from nmigen.sim import *


class Funct3:
    BEQ  = 0b000
    BNE  = 0b001
    BLT  = 0b100
    BGE  = 0b101
    BLTU = 0b110
    BGEU = 0b111


class Branch(Elaboratable):
    def __init__(self):
        self.funct3 = Signal(3)
        self.in1 = Signal(signed(32))
        self.in2 = Signal(signed(32))
        self.out = Signal(1)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.BEQ):
                m.d.comb += self.out.eq(self.in1 == self.in2)
            with m.Case(Funct3.BNE):
                m.d.comb += self.out.eq(self.in1 != self.in2)
            with m.Case(Funct3.BLT):
                m.d.comb += self.out.eq(self.in1 < self.in2)
            with m.Case(Funct3.BGE):
                m.d.comb += self.out.eq(self.in1 >= self.in2)
            with m.Case(Funct3.BLTU):
                m.d.comb += self.out.eq(self.in1 < self.in2)
            with m.Case(Funct3.BGEU):
                m.d.comb += self.out.eq(self.in1 >= self.in2)
        return m
