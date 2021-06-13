from nmigen import *
from nmigen.sim import *


class LoadStore(Elaboratable):
    def __init__(self):
        self.funct3 = Signal(3)
        self.address = Signal(2)
        self.sel = Signal(4)
        self.value_in = Signal(32)
        self.value_out = Signal(32)
        self.load = Signal()
        self.trap = Signal()

    def elaborate(self, platform):
        m = Module()

        mask = Signal(32)
        sign = Signal(1)
        value = Signal(32)

        with m.Switch(self.funct3[:2]):
            with m.Case('00'):
                m.d.comb += [
                    self.trap.eq(0),
                    self.sel.eq(0b1 << self.address),
                    mask.eq(0xff),
                    sign.eq(value[7]),
                ]
            with m.Case('01'):
                m.d.comb += [
                    self.trap.eq(self.address[0]),
                    self.sel.eq(0b11 << self.address),
                    mask.eq(0xffff),
                    sign.eq(value[15]),
                ]
            with m.Case('10'):
                m.d.comb += [
                    self.trap.eq(self.address[0] | self.address[1]),
                    self.sel.eq(0b1111),
                    mask.eq(0xffffffff),
                    sign.eq(0),
                ]

        with m.If(self.load):
            m.d.comb += value.eq(self.value_in >> (self.address << 3) & mask)
        with m.Else():
            m.d.comb += value.eq((self.value_in & mask) << (self.address << 3))

        with m.If(self.funct3[2] | ~sign):
            m.d.comb += self.value_out.eq(value)
        with m.Else():
            m.d.comb += self.value_out.eq(value | ~mask)

        return m
