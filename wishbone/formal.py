from nmigen import *
from nmigen.asserts import *
from nmigen.hdl.rec import *


def wishbone_layout(addr_width, data_width):
    return [
        ("cyc",   1,               DIR_FANOUT),
        ("stb",   1,               DIR_FANOUT),
        ("we",    1,               DIR_FANOUT),
        ("adr",   addr_width - 2,  DIR_FANOUT),
        ("dat_w", data_width,      DIR_FANOUT),
        ("sel",   data_width // 8, DIR_FANOUT),
        ("dat_r", data_width,      DIR_FANIN),
        ("ack",   1,               DIR_FANIN),
        ("stall", 1,               DIR_FANIN),
        ("err",   1,               DIR_FANIN)
    ]


def wishbone_formal_layout(bmc_depth):
    return [
        ("nreqs", bmc_depth, DIR_FANOUT),
        ("nacks", bmc_depth, DIR_FANOUT),
        ("outstanding", bmc_depth, DIR_FANOUT),
    ]


class WbMasterFormal(Elaboratable):
    def __init__(self, addr_width, data_width, bmc_depth):
        self.addr_width = addr_width
        self.data_width = data_width
        self.bmc_depth = bmc_depth

        self.wb = Record(wishbone_layout(addr_width, data_width))
        self.wbf = Record(wishbone_formal_layout(bmc_depth))

    def elaborate(self, platform):
        assert(platform == 'formal')

        m = Module()
        request = Signal(2 + self.addr_width + self.data_width + self.data_width // 8)
        m.d.comb += request.eq(Cat(self.wb.stb, self.wb.we, self.wb.adr, self.wb.dat_w, self.wb.sel))

        # The bus is initialized in a reset condition - no requests are being made and
        # the reset line is high.
        with m.If(Initial()):
            m.d.comb += [
                Assert(ResetSignal()),
                Assert(~self.wb.cyc),
                Assert(~self.wb.stb),
                Assume(~self.wb.ack),
                Assume(~self.wb.err),
            ]

        # On the clock following a reset, the bus must return to the idle state.
        with m.If(Past(ResetSignal())):
            m.d.comb += [
                Assert(~self.wb.cyc),
                Assert(~self.wb.stb),
                Assume(~self.wb.ack),
                Assume(~self.wb.err),
            ]

        # Signals can only change on the positive clock edge.
        with m.If(~Rose(ClockSignal())):
            m.d.comb += [
                #Assert(Stable(ResetSignal())),
                Assert(Stable(self.wb.cyc)),
                Assert(Stable(self.wb.stb)),
                Assert(Stable(self.wb.we)),
                Assert(Stable(self.wb.adr)),
                Assert(Stable(self.wb.dat_w)),
                Assert(Stable(self.wb.sel)),
                Assume(Stable(self.wb.ack)),
                Assume(Stable(self.wb.stall)),
                Assume(Stable(self.wb.dat_r)),
                Assume(Stable(self.wb.err)),
            ]

        # Bus master must drop the `cyc` line following any bus error signal.
        with m.If(Past(self.wb.err) & Past(self.wb.cyc)):
            m.d.comb += Assert(~self.wb.cyc)

        # stb can only be high when cyc is also high
        with m.If(self.wb.stb):
            m.d.comb += Assert(self.wb.cyc)

        # Once a request is placed onto the bus it cannot be changed until it is
        # accepted.
        with m.If(~Past(ResetSignal()) & Past(self.wb.stb) & Past(self.wb.stall) & self.wb.cyc):
            m.d.comb += [
                Assert(self.wb.stb),
                Assert(self.wb.we == Past(self.wb.we)),
                Assert(self.wb.adr == Past(self.wb.adr)),
                Assert(self.wb.sel == Past(self.wb.sel)),
            ]
            with m.If(self.wb.we):
                m.d.comb += Assert(self.wb.dat_w == Past(self.wb.dat_w))

        # Write enable shouldn't change from one request to the next.
        with m.If(Past(self.wb.stb) & self.wb.stb):
            m.d.comb += Assert(self.wb.we == Past(self.wb.we))

        # Within any given bus cycle, the direction may *only* change when there
        # are no further outstanding requests.
        with m.If(self.wbf.outstanding > 0):
            m.d.comb += Assert(self.wb.we == Past(self.wb.we))

        # Byte select determine which byes within a word should be written. To be
        # meaningful, any write transaction should assert one or more of these bits.
        with m.If(self.wb.stb & self.wb.we):
            m.d.comb += Assert(self.wb.sel.any())

        # When there is no bus cycle and no abort then both ack and err should be low
        # on the next clock.
        with m.If(~Past(self.wb.cyc) & ~self.wb.cyc):
            m.d.comb += [
                Assume(~self.wb.ack),
                Assume(~self.wb.err),
            ]

        # Ack and err may never be true on the same clock.
        m.d.comb += Assume(~self.wb.ack | ~self.wb.err)

        return m


class FaultyMaster(Elaboratable):
    def __init__(self, addr_width, data_width):
        self.addr_width = addr_width
        self.data_width = data_width


    def elaborate(self, platform):
        m = Module()
        wb = Record(wishbone_layout(self.addr_width, self.data_width))

        m.d.sync += [
            wb.cyc.eq(0),
            wb.stb.eq(0),
            wb.adr.eq(0),
            wb.sel.eq(0),
            wb.we.eq(0),
            wb.dat_w.eq(0),
        ]

        if platform == 'formal':
            formal = m.submodules.formal = WbMasterFormal(self.addr_width, self.data_width, bmc_depth=12)
            m.d.comb += [
                formal.wb.cyc.eq(wb.cyc),
                formal.wb.stb.eq(wb.stb),
                formal.wb.adr.eq(wb.adr),
                formal.wb.we.eq(wb.we),
                formal.wb.sel.eq(wb.sel),
                formal.wb.dat_w.eq(wb.dat_w),
                wb.dat_r.eq(formal.wb.dat_r),
                wb.stall.eq(formal.wb.stall),
                wb.ack.eq(formal.wb.ack),
                wb.err.eq(formal.wb.err),
            ]
            with m.If(Initial()):
                m.d.comb += ResetSignal().eq(1)
            with m.Else():
                m.d.comb += ResetSignal().eq(0)

        return m


def assertFormal(spec_dir, spec_name, spec, mode="bmc", solver='boolector', depth=1):
    from nmigen.back import rtlil
    import os
    import shutil
    import subprocess
    import textwrap
    import traceback
    #caller, *_ = traceback.extract_stack(limit=2)
    #spec_root, _ = os.path.splitext(caller.filename)
    #spec_dir = os.path.dirname(spec_root)
    #spec_name = "{}_{}".format(
    #    os.path.basename(spec_root).replace("test_", "spec_"),
    #    caller.name.replace("test_", "")
    #)

    # The sby -f switch seems not fully functional when sby is reading from stdin.
    if os.path.exists(os.path.join(spec_dir, spec_name)):
        shutil.rmtree(os.path.join(spec_dir, spec_name))

    if mode == "hybrid":
        # A mix of BMC and k-induction, as per personal communication with Claire Wolf.
        script = "setattr -unset init w:* a:nmigen.sample_reg %d"
        mode   = "bmc"
    else:
        script = ""

    config = textwrap.dedent("""\
    [options]
    mode {mode}
    depth {depth}
    wait on
    [engines]
    smtbmc {solver}
    [script]
    read_ilang top.il
    prep
    {script}
    [file top.il]
    {rtlil}
    """).format(
        mode=mode,
        depth=depth,
        solver=solver,
        script=script,
        rtlil=rtlil.convert(Fragment.get(spec, platform="formal"))
    )
    with subprocess.Popen([shutil.which("sby"), "-f", "-d", spec_name], cwd=spec_dir,
                          universal_newlines=True,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
        stdout, stderr = proc.communicate(config)
        if proc.returncode != 0:
            print('Formal verification failed:\n' + stdout)
            os.sys.exit(1)


if __name__ == '__main__':
    assertFormal('specs', 'faulty_master', FaultyMaster(32, 32), mode='bmc', solver='boolector', depth=12)
