from nmigen import *
from nmigen.hdl.rec import *
from nmigen.sim import *
from nmigen_soc import wishbone
from .alu import ALU
from .branch import Branch
from .decoder import Decoder, PcOp
from .gpio import Gpio
from .loadstore import LoadStore
from .regs import Registers
from .ram import RAM
from .rom import ROM

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
    def __init__(self, reset_address=0x8000_0000, with_rvfi=False):
        self.reset_address = reset_address
        self.with_rvfi = with_rvfi

        self.ibus = Record(wishbone_layout)
        self.dbus = Record(wishbone_layout)
        if with_rvfi:
            self.rvfi = Record(rvfi_layout)

    def elaborate(self, platform):
        m = Module()

        decoder   = m.submodules.decoder   = Decoder()
        regs      = m.submodules.regs      = Registers()
        alu       = m.submodules.alu       = ALU()
        branch    = m.submodules.branch    = Branch()
        loadstore = m.submodules.loadstore = LoadStore()

        pc = Signal(32, reset=self.reset_address)
        pc_next = Signal(32)
        pc_next_temp = Signal(32)
        pc_4 = Signal(32)
        inst = Signal(32)
        m.d.comb += pc_4.eq(pc + 4)
        rs1_en = Signal()
        rs2_en = Signal()
        rd_en = Signal()
        mem_addr = Signal(32)

        inst_addr_missaligned = Signal()
        illegal_inst = Signal()
        mem_addr_missaligned = Signal()
        valid = Signal()
        trap = Signal()

        m.d.comb += [
            self.ibus.adr.eq(pc[2:]),
            self.ibus.cyc.eq(1),
            decoder.inst.eq(self.ibus.dat_r),
            regs.rs1_addr.eq(decoder.rs1),
            regs.rs2_addr.eq(decoder.rs2),
            regs.rd_addr.eq(decoder.rd),
            alu.in1.eq(Mux(rs1_en, regs.rs1_data, pc)),
            alu.in2.eq(Mux(rs2_en, regs.rs2_data, decoder.imm)),
            branch.funct3.eq(decoder.funct3),
            branch.in1.eq(regs.rs1_data),
            branch.in2.eq(regs.rs2_data),
            loadstore.funct3.eq(decoder.funct3),
            loadstore.address.eq(mem_addr[:2]),
            loadstore.value_in.eq(Mux(decoder.mem_op_store, regs.rs2_data, self.dbus.dat_r)),
            loadstore.load.eq(decoder.mem_op_en & ~decoder.mem_op_store),
            self.dbus.adr.eq(mem_addr[2:]),
            self.dbus.sel.eq(loadstore.sel),
            self.dbus.dat_w.eq(loadstore.value_out),
            self.dbus.cyc.eq(1),
            illegal_inst.eq(decoder.trap),
            inst_addr_missaligned.eq(pc_next_temp[0] | pc_next_temp[1]),
            mem_addr_missaligned.eq(loadstore.trap),
            trap.eq(inst_addr_missaligned | illegal_inst | mem_addr_missaligned),
            pc_next.eq(Mux(trap, pc, pc_next_temp)),
            rd_en.eq(decoder.rd_en & ~decoder.mem_op_en),
        ]

        with m.Switch(decoder.pc_op):
            with m.Case(PcOp.NEXT):
                m.d.comb += [
                    alu.funct4.eq(Cat(decoder.funct1, decoder.funct3)),
                    rs1_en.eq(decoder.rs1_en),
                    rs2_en.eq(decoder.rs2_en),
                    pc_next_temp.eq(pc_4),
                    regs.rd_data.eq(alu.out),
                ]
                with m.If(decoder.mem_op_en):
                    m.d.comb += [
                        alu.funct4.eq(0),
                        rs2_en.eq(0),
                    ]
            with m.Case(PcOp.JAL):
                m.d.comb += [
                    rs1_en.eq(0),
                    rs2_en.eq(0),
                    pc_next_temp.eq(alu.out),
                    regs.rd_data.eq(pc_4),
                ]
            with m.Case(PcOp.JALR):
                m.d.comb += [
                    rs1_en.eq(1),
                    rs2_en.eq(0),
                    pc_next_temp.eq(alu.out),
                    regs.rd_data.eq(pc_4),
                ]
            with m.Case(PcOp.BRANCH):
                m.d.comb += [
                    alu.funct4.eq(0),
                    rs1_en.eq(0),
                    rs2_en.eq(0),
                    pc_next_temp.eq(Mux(branch.out, alu.out, pc_4)),
                ]

        with m.FSM():
            with m.State('FETCH'):
                m.d.comb += self.ibus.stb.eq(1)
                with m.If(self.ibus.ack):
                    m.next = 'EXECUTE'
                    m.d.sync += inst.eq(self.ibus.dat_r)
                    m.d.comb += decoder.inst.eq(self.ibus.dat_r)
            with m.State('EXECUTE'):
                m.d.comb += decoder.inst.eq(inst)
                with m.If(trap):
                    m.next = 'FETCH'
                    m.d.comb += valid.eq(0)
                    m.d.sync += pc.eq(pc_next)
                with m.Elif(decoder.mem_op_en):
                    m.next = 'WRITE'
                with m.Else():
                    m.next = 'FETCH'
                    m.d.comb += [
                        regs.rd_we.eq(1),
                        valid.eq(1),
                    ]
                    m.d.sync += pc.eq(pc_next)
            with m.State('WRITE'):
                m.d.comb += [
                    decoder.inst.eq(inst),
                    mem_addr.eq(alu.out),
                    self.dbus.stb.eq(1),
                    self.dbus.we.eq(decoder.mem_op_store),
                ]
                with m.If(self.dbus.ack):
                    m.next = 'FETCH'
                    m.d.comb += [
                        valid.eq(1),
                        regs.rd_we.eq(~decoder.mem_op_store),
                        regs.rd_data.eq(loadstore.value_out),
                    ]
                    m.d.sync += pc.eq(pc_next)

        if hasattr(self, 'rvfi'):
            m.d.comb += [
                self.rvfi.halt.eq(0),
                self.rvfi.mode.eq(Const(3)), # M-mode
                self.rvfi.ixl.eq(Const(1)), # XLEN=32
                self.rvfi.intr.eq(0),
                self.rvfi.valid.eq(valid),
                self.rvfi.trap.eq(trap),

                self.rvfi.pc_rdata.eq(pc),
                self.rvfi.pc_wdata.eq(pc_next),
                self.rvfi.insn.eq(inst),
                self.rvfi.rs1_addr.eq(decoder.rs1),
                self.rvfi.rs1_rdata.eq(regs.rs1_data),
                self.rvfi.rs2_addr.eq(decoder.rs2),
                self.rvfi.rs2_rdata.eq(regs.rs2_data),
                self.rvfi.rd_addr.eq(decoder.rd),
                self.rvfi.rd_wdata.eq(Mux(decoder.rd_en & (regs.rd_addr != 0), regs.rd_data, 0)),
                self.rvfi.trap.eq(trap),

                # Memory Access
                self.rvfi.mem_addr.eq(Mux(decoder.mem_op_en, Cat(0, 0, mem_addr[2:]), 0)),
                self.rvfi.mem_rmask.eq(Mux(decoder.mem_op_en & ~decoder.mem_op_store, loadstore.sel, 0)),
                self.rvfi.mem_wmask.eq(Mux(decoder.mem_op_en & decoder.mem_op_store, loadstore.sel, 0)),
                self.rvfi.mem_rdata.eq(Mux(decoder.mem_op_en & ~decoder.mem_op_store, self.dbus.dat_r, 0)),
                self.rvfi.mem_wdata.eq(Mux(decoder.mem_op_en & decoder.mem_op_store, self.dbus.dat_w, 0)),
            ]
            with m.If(self.rvfi.valid):
                m.d.sync += self.rvfi.order.eq(self.rvfi.order + 1)

        return m


class Top(Elaboratable):
    def __init__(self, prog, with_rvfi=False):
        self.cpu = RV32(with_rvfi=with_rvfi)
        self.bus = wishbone.Decoder(addr_width = 32, data_width = 32)
        self.rom = ROM(prog)
        self.ram = RAM(32)
        self.gpio = Gpio()
        self.clk = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.cpu  = self.cpu
        m.submodules.bus  = self.bus
        m.submodules.gpio = self.gpio
        m.submodules.rom  = self.rom
        m.submodules.ram  = self.ram

        self.bus.add(self.ram, addr = 0x4000 >> 2)
        self.bus.add(self.gpio, addr = 0x5000 >> 2)
        bus = self.bus.bus

        #por = ClockDomain(reset_less=True)
        #sync = ClockDomain()
        #m.domains += por
        #m.domains += sync
        #delay = Signal(8, reset = 255)
        #with m.If(delay != 0):
        #    m.d.por += delay.eq(delay - 1)

        m.d.comb += [
            #ClockSignal().eq(por.clk),
            #ResetSignal().eq(delay != 0),

            self.rom.cyc.eq(self.cpu.ibus.cyc),
            self.rom.stb.eq(self.cpu.ibus.stb),
            self.rom.adr.eq(self.cpu.ibus.adr),
            self.cpu.ibus.ack.eq(self.rom.ack),
            self.cpu.ibus.dat_r.eq(self.rom.dat_r),

            bus.cyc.eq(self.cpu.dbus.cyc),
            bus.stb.eq(self.cpu.dbus.stb),
            bus.adr.eq(self.cpu.dbus.adr),
            bus.dat_w.eq(self.cpu.dbus.dat_w),
            bus.we.eq(self.cpu.dbus.we),
            self.cpu.dbus.ack.eq(bus.ack),
            self.cpu.dbus.dat_r.eq(bus.dat_r),
        ]

        #if platform is not None:
        #    clk = platform.request('clk12')
        #    m.d.comb += self.clk.eq(clk)

        return m

def read_prog(path):
    prog = []
    with open(path, 'rb') as f:
        while True:
            b = f.read(4)
            if b == b'':
                break
            i = int.from_bytes(b, byteorder='little', signed=False)
            prog.append(i)
    return prog

if __name__ == '__main__':
    '''
    prog = [
        0xdead_c0b7, # lui   x1, 0xdeadc
        0xeef0_8093, # addi  x1, x1,-273
        0x8000_4197, # auipc x3,0x80004
        0xfe11_ac23, # sw    x1,-8(x3) # 0x4000
        0x8000_4117, # auipc x2,0x80004
        0xff01_2103, # lw    x2,-16(x2) # 0x4000
        0x0011_0463, # beq   x2,x1,80000020
        0x0000_0073, # ecall
        0x0000_0013, # addi x0,x0,0
    ]
    '''

    #prog = read_prog('./tests/store_load.bin')
    prog = read_prog('./tests/gpio.bin')

    dut = Top(prog, with_rvfi=True)
    sim = Simulator(dut)
    rvfi = dut.cpu.rvfi
    assert_en = False
    with sim.write_vcd('rv32.vcd'):
        def step():
            clock = 0
            yield Tick()
            yield Settle()
            while (yield rvfi.valid) != 1 and clock < 5:
                assert(yield rvfi.trap != 1)
                clock += 1
                yield Tick()
                yield Settle()
            assert(clock < 8)

        def proc():
            yield from step()
            reset_address = 0x8000_0000
            if assert_en:
                assert(yield rvfi.pc_rdata == reset_address)
                assert(yield rvfi.pc_wdata == reset_address + 4)
                assert(yield rvfi.insn == prog[0])
                assert(yield rvfi.rs1_addr == 0)
                assert(yield rvfi.rs1_rdata == 0)
                assert(yield rvfi.rs2_addr == 0)
                assert(yield rvfi.rs2_rdata == 0)
                assert(yield rvfi.rd_addr == 1)
                assert(yield rvfi.rd_wdata == 0xdeadc000)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[1])
                assert(yield rvfi.rs1_addr == 1)
                assert(yield rvfi.rs1_rdata == 0xdeadc000)
                assert(yield rvfi.rs2_addr == 0)
                assert(yield rvfi.rs2_rdata == 0)
                assert(yield rvfi.rd_addr == 1)
                assert(yield rvfi.rd_wdata == 0xdeadbeef)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[2])
                assert(yield rvfi.rs1_addr == 0)
                assert(yield rvfi.rs1_rdata == 0)
                assert(yield rvfi.rs2_addr == 0)
                assert(yield rvfi.rs2_rdata == 0)
                assert(yield rvfi.rd_addr == 3)
                assert(yield rvfi.rd_wdata == 0x4008)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[3])
                assert(yield rvfi.rs2_addr == 1)
                assert(yield rvfi.rs2_rdata == 0xdeadbeef)
                assert(yield rvfi.mem_addr == 0x4000)
                assert(yield rvfi.mem_wdata == 0xdead_beef)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[4])
                assert(yield rvfi.rs1_addr == 0)
                assert(yield rvfi.rs1_rdata == 0)
                assert(yield rvfi.rs2_addr == 0)
                assert(yield rvfi.rs2_rdata == 0)
                assert(yield rvfi.rd_addr == 2)
                assert(yield rvfi.rd_wdata == 0x4010)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[5])
                assert(yield rvfi.rd_addr == 2)
                assert(yield rvfi.rd_wdata == 0xdeadbeef)
                assert(yield rvfi.mem_addr == 0x4000)
                assert(yield rvfi.mem_rdata == 0xdead_beef)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[6])
                assert(yield rvfi.rs1_addr == 2)
                assert(yield rvfi.rs1_rdata == 0xdeadbeef)
                assert(yield rvfi.rs2_addr == 1)
                assert(yield rvfi.rs2_rdata == 0xdeadbeef)
                assert(yield rvfi.rd_addr == 0)
                assert(yield rvfi.rd_wdata == 0)
                assert(yield rvfi.pc_wdata == reset_address + 32)

            yield from step()
            if assert_en:
                assert(yield rvfi.insn == prog[8])

            yield Tick()
            yield Tick()
            yield Tick()
            yield Tick()
            yield Settle()

        sim.add_clock(1e-6, domain='sync')
        sim.add_sync_process(proc)
        sim.run()
