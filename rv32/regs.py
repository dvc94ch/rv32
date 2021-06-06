from nmigen import *
from nmigen.sim import *

class Registers(Elaboratable):
    def __init__(self):
        self.rs1_addr = Signal(5)
        self.rs1_data = Signal(32)
        self.rs2_addr = Signal(5)
        self.rs2_data = Signal(32)
        self.rd_addr = Signal(5)
        self.rd_data = Signal(32)
        self.rd_we = Signal()

    def elaborate(self, platform):
        m = Module()

        regfile = Memory(width = 32, depth = 32)
        rs1 = m.submodules.rs1 = regfile.read_port()
        rs2 = m.submodules.rs2 = regfile.read_port()
        rd  = m.submodules.rd  = regfile.write_port()

        m.d.comb += [
            rs1.addr.eq(self.rs1_addr),
            self.rs1_data.eq(rs1.data),
            rs2.addr.eq(self.rs2_addr),
            self.rs2_data.eq(rs2.data),
        ]

        with m.If(self.rd_addr != 0):
            m.d.comb += [
                rd.addr.eq(self.rd_addr),
                rd.data.eq(self.rd_data),
                rd.en.eq(self.rd_we),
            ]

        return m

def test_regs(reg, data, res):
    dut = Registers()
    sim = Simulator(dut)

    with sim.write_vcd('regs.vcd'):
        def proc():
            yield dut.rd_addr.eq(reg)
            yield dut.rd_data.eq(data)
            yield dut.rd_we.eq(1)
            #yield Tick()
            yield dut.rs1_addr.eq(reg)
            yield dut.rs2_addr.eq(reg)
            yield Tick()
            yield Settle()
            rs1_data = yield dut.rs1_data
            rs2_data = yield dut.rs2_data
            if rs1_data != res:
                raise ValueError('rs1_data: %s expected %s but got %s' % (reg, res, rs1_data))
            if rs2_data != res:
                raise ValueError('rs2_data: %s expected %s but got %s' % (reg, res, rs2_data))

    sim.add_clock(1e-6)
    sim.add_sync_process(proc)
    sim.run()

if __name__ == '__main__':
    for reg in range(32):
        if reg == 0:
            test_regs(reg, 0xffff_ffff, 0)
        else:
            test_regs(reg, 0xffff_ffff, 0xffff_ffff)
