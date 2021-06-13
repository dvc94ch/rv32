from nmigen import *
from nmigen.sim import *
from nmigen_soc.memory import *
from nmigen_soc.wishbone import *


class Gpio(Elaboratable, Interface):
    def __init__(self):
        Interface.__init__(self, data_width = 32, addr_width = 1)
        self.memory_map = MemoryMap(data_width = 32, addr_width = 1, alignment = 0)

    def elaborate(self, platform):
        m = Module()
        leds = Signal(8)
        m.d.sync += self.ack.eq(0)
        m.d.comb += self.dat_r.eq(leds)
        with m.If(self.cyc):
            m.d.sync += self.ack.eq(self.stb)
            with m.If(self.we):
                m.d.sync += leds.eq(self.dat_w),

        if platform is not None:
            for i in range(8):
                led = platform.request("led", i)
                m.d.comb += led.o.eq(leds[i])

        return m
