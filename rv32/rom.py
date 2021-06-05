from math import ceil, log2
from nmigen import *
from nmigen.sim import *
from nmigen_soc.memory import *
from nmigen_soc.wishbone import *

class ROM(Elaboratable, Interface):
    def __init__(self, data):
        self.size = len(data)
        self.data = Memory(width = 32, depth = self.size, init = data)
        self.r = self.data.read_port()

        Interface.__init__(self, data_width = 32, addr_width = ceil(log2(self.size + 1)))
        self.memory_map = MemoryMap(data_width = self.data_width,
                                    addr_width = self.addr_width,
                                    alignment = 0)

    def elaborate(self, platform):
        m = Module()
        m.submodules.r = self.r
        m.d.sync += self.ack.eq(0)
        with m.If(self.cyc):
            m.d.sync += self.ack.eq(self.stb)
        m.d.comb += [
            self.r.addr.eq(self.adr),
            self.dat_r.eq(self.r.data)
        ]
        return m

def rom_read_ut(rom, address, expected):
    yield rom.adr.eq(address)
    yield Tick()
    yield Settle()
    assert(yield rom.ack)
    actual = yield rom.dat_r
    if expected == actual:
        print("PASS: Memory[0x%04X] = 0x%08X" % (address, expected))
    else:
        print("FAIL: Memory[0x%04X] = 0x%08X (got: 0x%08X)" % (address, expected, actual))

if __name__ == "__main__":
    dut = ROM([0x01234567, 0x89ABCDEF,
               0x0C0FFEE0, 0xDEC0FFEE,
               0xFEEBEEDE])
    sim = Simulator(dut)
    with sim.write_vcd('rom.vcd'):
        def proc():
            yield dut.cyc.eq(1)
            yield dut.stb.eq(1)
            yield from rom_read_ut(dut, 0, 0x01234567)
            yield from rom_read_ut(dut, 1, 0x89ABCDEF)
            yield from rom_read_ut(dut, 2, 0x0C0FFEE0)
            yield from rom_read_ut(dut, 3, 0xDEC0FFEE)
            yield from rom_read_ut(dut, 4, 0xFEEBEEDE)
        sim.add_clock(1e-6)
        sim.add_sync_process(proc)
        sim.run()
