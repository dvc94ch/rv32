from math import ceil, log2
from nmigen import *
from nmigen.sim import *
from nmigen_soc.memory import *
from nmigen_soc.wishbone import *

class RAM(Elaboratable, Interface):
    def __init__(self, depth):
        self.depth = depth
        self.data = Memory(width = 32, depth = depth)
        self.r = self.data.read_port()
        self.w = self.data.write_port()

        Interface.__init__(self, data_width = 32, addr_width = ceil(log2(self.depth)))
        self.memory_map = MemoryMap(data_width = self.data_width,
                                    addr_width = self.addr_width,
                                    alignment = 0)

    def elaborate(self, platform):
        m = Module()
        m.submodules.r = self.r
        m.submodules.w = self.w
        m.d.sync += self.ack.eq(0)
        with m.If(self.cyc):
            m.d.sync += self.ack.eq(self.stb)
        m.d.comb += [
            self.r.addr.eq(self.adr),
            self.w.addr.eq(self.adr),
            self.dat_r.eq(self.r.data),
            self.w.data.eq(self.dat_w),
            self.w.en.eq(self.we),
        ]
        return m

def wishbone_cycle(ram):
    yield ram.stb.eq(1)
    while (yield ram.ack) == 0:
        yield Tick()
        yield Settle()
    yield ram.stb.eq(0)
    yield Tick()
    yield Settle()
    assert((yield ram.ack) == 0)

def ram_read_ut(ram, address, expected):
    yield ram.adr.eq(address)
    yield ram.we.eq(0)
    yield from wishbone_cycle(ram)
    assert_mem(address, expected, (yield ram.dat_r))

def ram_write_ut(ram, address, value):
    yield ram.adr.eq(address)
    yield ram.dat_w.eq(value)
    yield ram.we.eq(1)
    yield from wishbone_cycle(ram)

def assert_mem(address, expected, actual):
    if expected == actual:
        print("PASS: Memory[0x%04X] = 0x%08X" % (address, expected))
    else:
        print("FAIL: Memory[0x%04X] = 0x%08X (got: 0x%08X)" % (address, expected, actual))


if __name__ == "__main__":
    dut = RAM(32)
    sim = Simulator(dut)
    with sim.write_vcd('vcd/ram.vcd'):
        def proc():
            yield dut.cyc.eq(1)
            yield from ram_write_ut(dut, 0, 0x01234567)
            yield from ram_write_ut(dut, 1, 0x89ABCDEF)
            yield from ram_read_ut(dut, 0, 0x01234567)
            yield from ram_read_ut(dut, 0, 0x01234567)
            yield from ram_write_ut(dut, 2, 0x01234567)
            yield from ram_read_ut(dut, 1, 0x89ABCDEF)
        sim.add_clock(1e-6)
        sim.add_sync_process(proc)
        sim.run()
