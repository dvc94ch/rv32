from nmigen import *

class RV32(Elaboratable):
    def __init__(self, prog):
        self.prog = prog
        self.pc = Signal(32)

        self.rom = Memory(width = 32, depth = len(self.prog), init = self.prog)
        self.icache = self.rom.read_port()

        self.ram = Memory(width = 32, depth = 512)
        self.dcache_r = self.ram.read_port()
        self.dcache_w = self.ram.write_port()

        self.regfile = Memory(width = 32, depth = 32)
        self.rs1 = self.regfile.read_port()
        self.rs2 = self.regfile.read_port()
        self.rd = self.regfile.write_port()

    def elaborate(self, platform):
        m = Module()

        m.submodules.icache = self.icache
        m.submodules.dcache_r = self.dcache_r
        m.submodules.dcache_w = self.dcache_w
        m.submodules.rs1 = self.rs1
        m.submodules.rs2 = self.rs2
        m.submodules.rd = self.rd

        decoder = Decoder()
        m.submodules.decoder = decoder

        m.d.comb += [
            self.icache.addr.eq(self.pc[2:]),
            decoder.inst.eq(self.icache.data),
            self.rs1.addr.eq(decoder.rs1),
            self.rs2.addr.eq(decoder.rs2),
            self.rd.addr.eq(decoder.rd),
        ]

        alu = ALU()
        m.submodules.alu = alu
        m.d.comb += [
            alu.funct4.eq(decoder.funct4),
            alu.in1.eq(self.rs1.data),
            self.rd.data.eq(alu.out),
            self.rd.en.eq(1),
        ]
        with m.If(decoder.rs2_reg_en):
            m.d.sync += alu.in2.eq(self.rs2.data)
        with m.Else():
            m.d.sync += alu.in2.eq(decoder.imm)

        m.d.sync += [
            self.pc.eq(self.pc + 4)
        ]

        return m

class Decoder(Elaboratable):
    def __init__(self):
        self.inst = Signal(32)
        self.imm = Signal(32)
        self.rs1 = Signal(5)
        self.rs2 = Signal(5)
        self.rd = Signal(5)
        self.funct4 = Signal(4)
        self.rs2_reg_en = Signal()

    def elaborate(self, platform):
        m = Module()
        inst = self.inst
        m.d.comb += [
            self.rs1.eq(inst[15:20]),
            self.rs2.eq(inst[20:25]),
            self.rd.eq(inst[7:12]),
            # funct3 + bit 30
            self.funct4.eq(Cat(inst[12:15], inst[30])),
        ]

        imm_i = Signal(32)
        imm_s = Signal(32)
        imm_b = Signal(32)
        imm_u = Signal(32)
        imm_j = Signal(32)
        m.d.comb += [
            imm_i.eq(Cat(inst[20], inst[21:25], inst[25:31], Repl(inst[31], 21))),
            imm_s.eq(Cat(inst[7], inst[8:12], inst[25:31], Repl(inst[31], 21))),
            imm_b.eq(Cat(0, inst[8:12], inst[25:31], inst[7], Repl(inst[31], 20))),
            imm_u.eq(Cat(Repl(0, 12), inst[12:20], inst[20:31], inst[31])),
            imm_j.eq(Cat(0, inst[21:25], inst[25:31], inst[20], inst[12:19], Repl(inst[31], 12))),
        ]
        with m.Switch(inst[2:7]):
            with m.Case(Opcode.LUI):
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
                m.d.comb += self.imm.eq(imm_s)
            with m.Case(Opcode.IMM):
                m.d.comb += self.imm.eq(imm_i)
            with m.Case(Opcode.REG):
                m.d.comb += self.rs2_reg_en.eq(1)
        return m

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
        self.in1 = Signal(32)
        self.in2 = Signal(32)
        self.out = Signal(32)

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
                # TODO
                pass
            with m.Case(Funct4.SLTU):
                # TODO
                pass
            with m.Case(Funct4.XOR):
                m.d.comb += self.out.eq(self.in1 ^ self.in2)
            with m.Case(Funct4.SRL):
                m.d.comb += self.out.eq(self.in1 >> self.in2[:5])
            with m.Case(Funct4.SRA):
                # TODO
                pass
            with m.Case(Funct4.OR):
                m.d.comb += self.out.eq(self.in1 | self.in2)
            with m.Case(Funct4.AND):
                m.d.comb += self.out.eq(self.in1 & self.in2)
        return m

if __name__ == '__main__':
    from nmigen.sim import *
    prog = [
        0b000000000001_00000_000_00001_0010011, # addi x1, x0, 1
        0b000000000001_00001_000_00001_0010011, # addi x1, x1, 1
        0b000000000001_00001_000_00001_0010011, # addi x1, x1, 1
    ]
    dut = RV32(prog)
    sim = Simulator(dut)
    with sim.write_vcd('rv32.vcd'):
        def proc():
            yield Settle()
            assert(yield dut.pc == 4)
            assert(yield dut.icache.data == prog[0])
            assert(yield dut.rs1.addr == 0)
            # don't care about rs2 as the immediate value is used
            yield Tick()
            yield Settle()
            assert(yield dut.rs1.data == 0)
            assert(yield dut.rd.addr == 1)
            assert(yield dut.rd.data == 1)

            assert(yield dut.pc == 8)
            assert(yield dut.icache.data == prog[1])
            assert(yield dut.rs1.addr == 1)
            # don't care about rs2 as the immediate value is used
            yield Tick()
            yield Settle()
            assert(yield dut.rs1.data == 1)
            assert(yield dut.rd.addr == 1)
            assert(yield dut.rd.data == 2)

            assert(yield dut.pc == 12)
            assert(yield dut.icache.data == prog[2])
            assert(yield dut.rs1.addr == 1)
            # don't care about rs2 as the immediate value is used
            yield Tick()
            yield Settle()
            assert(yield dut.rs1.data == 2)
            assert(yield dut.rd.addr == 1)
            assert(yield dut.rd.data == 3)

        sim.add_clock(1e-6)
        sim.add_sync_process(proc)
        sim.run()
