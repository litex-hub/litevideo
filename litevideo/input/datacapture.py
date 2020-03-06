from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BusSynchronizer
from migen.genlib.misc import WaitTimer
from migen.genlib.cdc import MultiReg, Gearbox

from litex.soc.interconnect.csr import *


class S6DataCapture(Module, AutoCSR):
    def __init__(self, pad_p, pad_n, ntbits=8):
        self.serdesstrobe = Signal()
        self.d = Signal(10)

        self._dly_ctl = CSR(6)
        self._dly_busy = CSRStatus(2)
        self._phase = CSRStatus(2)
        self._phase_reset = CSR()

        # # #

        # IO
        pad_se = Signal()
        self.specials += Instance("IBUFDS",
                                  i_I=pad_p, i_IB=pad_n,
                                  o_O=pad_se)

        pad_delayed_master = Signal()
        pad_delayed_slave = Signal()
        delay_inc = Signal()
        delay_ce = Signal()
        delay_master_cal = Signal()
        delay_master_rst = Signal()
        delay_master_busy = Signal()
        delay_slave_cal = Signal()
        delay_slave_rst = Signal()
        delay_slave_busy = Signal()
        self.specials += [
            Instance("IODELAY2",
                p_SERDES_MODE="MASTER",
                p_DELAY_SRC="IDATAIN", p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                p_COUNTER_WRAPAROUND="STAY_AT_LIMIT", p_DATA_RATE="SDR",

                i_IDATAIN=pad_se, o_DATAOUT=pad_delayed_master,
                i_CLK=ClockSignal("pix2x"), i_IOCLK0=ClockSignal("pix10x"),

                i_INC=delay_inc, i_CE=delay_ce,
                i_CAL=delay_master_cal, i_RST=delay_master_rst, o_BUSY=delay_master_busy,
                i_T=1),
            Instance("IODELAY2",
                p_SERDES_MODE="SLAVE",
                p_DELAY_SRC="IDATAIN", p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                p_COUNTER_WRAPAROUND="WRAPAROUND", p_DATA_RATE="SDR",

                i_IDATAIN=pad_se, o_DATAOUT=pad_delayed_slave,
                i_CLK=ClockSignal("pix2x"), i_IOCLK0=ClockSignal("pix10x"),

                i_INC=delay_inc, i_CE=delay_ce,
                i_CAL=delay_slave_cal, i_RST=delay_slave_rst, o_BUSY=delay_slave_busy,
                i_T=1)
        ]

        dsr2 = Signal(5)
        pd_valid = Signal()
        pd_incdec = Signal()
        pd_edge = Signal()
        pd_cascade = Signal()
        self.specials += [
            Instance("ISERDES2",
                p_SERDES_MODE="MASTER",
                p_BITSLIP_ENABLE="FALSE", p_DATA_RATE="SDR", p_DATA_WIDTH=5,
                p_INTERFACE_TYPE="RETIMED",

                i_D=pad_delayed_master,
                o_Q4=dsr2[4], o_Q3=dsr2[3], o_Q2=dsr2[2], o_Q1=dsr2[1],

                i_BITSLIP=0, i_CE0=1, i_RST=0,
                i_CLK0=ClockSignal("pix10x"), i_CLKDIV=ClockSignal("pix2x"),
                i_IOCE=self.serdesstrobe,

                o_VALID=pd_valid, o_INCDEC=pd_incdec,
                i_SHIFTIN=pd_edge, o_SHIFTOUT=pd_cascade),
            Instance("ISERDES2",
                p_SERDES_MODE="SLAVE",
                p_BITSLIP_ENABLE="FALSE", p_DATA_RATE="SDR", p_DATA_WIDTH=5,
                p_INTERFACE_TYPE="RETIMED",

                i_D=pad_delayed_slave,
                o_Q4=dsr2[0],

                i_BITSLIP=0, i_CE0=1, i_RST=0,
                i_CLK0=ClockSignal("pix10x"), i_CLKDIV=ClockSignal("pix2x"),
                i_IOCE=self.serdesstrobe,

                i_SHIFTIN=pd_cascade, o_SHIFTOUT=pd_edge)
        ]

        # Phase error accumulator
        lateness = Signal(ntbits, reset=2**(ntbits - 1))
        too_late = Signal()
        too_early = Signal()
        reset_lateness = Signal()
        self.comb += [
            too_late.eq(lateness == (2**ntbits - 1)),
            too_early.eq(lateness == 0)
        ]
        self.sync.pix2x += [
            If(reset_lateness,
                lateness.eq(2**(ntbits - 1))
            ).Elif(~delay_master_busy & ~delay_slave_busy & ~too_late & ~too_early,
                If(pd_valid & pd_incdec, lateness.eq(lateness - 1)),
                If(pd_valid & ~pd_incdec, lateness.eq(lateness + 1))
            )
        ]

        # Delay control
        self.submodules.delay_master_done = PulseSynchronizer("pix2x", "sys")
        delay_master_pending = Signal()
        self.sync.pix2x += [
            self.delay_master_done.i.eq(0),
            If(~delay_master_pending,
                If(delay_master_cal | delay_ce, delay_master_pending.eq(1))
            ).Else(
                If(~delay_master_busy,
                    self.delay_master_done.i.eq(1),
                    delay_master_pending.eq(0)
                )
            )
        ]
        self.submodules.delay_slave_done = PulseSynchronizer("pix2x", "sys")
        delay_slave_pending = Signal()
        self.sync.pix2x += [
            self.delay_slave_done.i.eq(0),
            If(~delay_slave_pending,
                If(delay_slave_cal | delay_ce, delay_slave_pending.eq(1))
            ).Else(
                If(~delay_slave_busy,
                    self.delay_slave_done.i.eq(1),
                    delay_slave_pending.eq(0)
                )
            )
        ]

        self.submodules.do_delay_master_cal = PulseSynchronizer("sys", "pix2x")
        self.submodules.do_delay_master_rst = PulseSynchronizer("sys", "pix2x")
        self.submodules.do_delay_slave_cal = PulseSynchronizer("sys", "pix2x")
        self.submodules.do_delay_slave_rst = PulseSynchronizer("sys", "pix2x")
        self.submodules.do_delay_inc = PulseSynchronizer("sys", "pix2x")
        self.submodules.do_delay_dec = PulseSynchronizer("sys", "pix2x")
        self.comb += [
            delay_master_cal.eq(self.do_delay_master_cal.o),
            delay_master_rst.eq(self.do_delay_master_rst.o),
            delay_slave_cal.eq(self.do_delay_slave_cal.o),
            delay_slave_rst.eq(self.do_delay_slave_rst.o),
            delay_inc.eq(self.do_delay_inc.o),
            delay_ce.eq(self.do_delay_inc.o | self.do_delay_dec.o),
        ]

        sys_delay_master_pending = Signal()
        self.sync += [
            If(self.do_delay_master_cal.i |
               self.do_delay_inc.i |
               self.do_delay_dec.i,
                sys_delay_master_pending.eq(1)
            ).Elif(self.delay_master_done.o,
                sys_delay_master_pending.eq(0)
            )
        ]
        sys_delay_slave_pending = Signal()
        self.sync += [
            If(self.do_delay_slave_cal.i |
               self.do_delay_inc.i |
               self.do_delay_dec.i,
                sys_delay_slave_pending.eq(1)
            ).Elif(self.delay_slave_done.o,
                sys_delay_slave_pending.eq(0)
            )
        ]

        self.comb += [
            self.do_delay_master_cal.i.eq(self._dly_ctl.re & self._dly_ctl.r[0]),
            self.do_delay_master_rst.i.eq(self._dly_ctl.re & self._dly_ctl.r[1]),
            self.do_delay_slave_cal.i.eq(self._dly_ctl.re & self._dly_ctl.r[2]),
            self.do_delay_slave_rst.i.eq(self._dly_ctl.re & self._dly_ctl.r[3]),
            self.do_delay_inc.i.eq(self._dly_ctl.re & self._dly_ctl.r[4]),
            self.do_delay_dec.i.eq(self._dly_ctl.re & self._dly_ctl.r[5]),
            self._dly_busy.status.eq(Cat(sys_delay_master_pending,
                                         sys_delay_slave_pending))
        ]

        # Phase detector control
        self.specials += MultiReg(Cat(too_late, too_early), self._phase.status)
        self.submodules.do_reset_lateness = PulseSynchronizer("sys", "pix2x")
        self.comb += [
            reset_lateness.eq(self.do_reset_lateness.o),
            self.do_reset_lateness.i.eq(self._phase_reset.re)
        ]

        # 5:10 deserialization
        dsr = Signal(10)
        self.sync.pix2x += dsr.eq(Cat(dsr[5:], dsr2))
        if hasattr(pad_p, "inverted"):
            self.sync.pix += self.d.eq(~dsr)
        else:
            self.sync.pix += self.d.eq(dsr)


class S7PhaseDetector(Module, AutoCSR):
    def __init__(self):
        self.mdata = Signal(8)
        self.sdata = Signal(8)

        self.inc = Signal()
        self.dec = Signal()

        # # #

        # ideal sampling (middle of the eye):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #    +     +     +     +     +     +      master sampling
        #       -     -     -     -     -     -   slave sampling (90°/bit period)
        # Since taps are fixed length delays, this ideal case is not possible
        # and we will fall in the 2 following possible cases:
        #
        # 1) too late sampling (idelay needs to be decremented):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #     +     +     +     +     +     +     master sampling
        #        -     -     -     -     -     -  slave sampling (90°/bit period)
        # on mdata transition, mdata != sdata
        #
        #
        # 2) too early sampling (idelay needs to be incremented):
        #  _____       _____       _____
        # |     |_____|     |_____|     |_____|   data
        #   +     +     +     +     +     +       master sampling
        #      -     -     -     -     -     -    slave sampling (90°/bit period)
        # on mdata transition, mdata == sdata

        transition = Signal()
        inc = Signal()
        dec = Signal()

        # find transition
        mdata_d = Signal(8)
        self.sync.pix1p25x += mdata_d.eq(self.mdata)
        self.comb += transition.eq(mdata_d != self.mdata)


        # find what to do
        self.comb += [
            self.inc.eq(transition & (self.mdata == self.sdata)),
            self.dec.eq(transition & (self.mdata != self.sdata))
        ]


class S7DataCapture(Module, AutoCSR):
    def __init__(self, pad_p, pad_n, ntbits=8):
        self.d = Signal(10)

        self._dly_ctl = CSR(5)
        self._phase = CSRStatus(2)
        self._phase_reset = CSR()
        self._cntvalueout_m = CSRStatus(5)
        self._cntvalueout_s = CSRStatus(5)

        # # #

        # use 2 serdes for phase detection: master & slave
        serdes_m_i_nodelay = Signal()
        serdes_s_i_nodelay = Signal()
        self.specials += [
            Instance("IBUFDS_DIFF_OUT",
                i_I=pad_p,
                i_IB=pad_n,
                o_O=serdes_m_i_nodelay,
                o_OB=serdes_s_i_nodelay,
            )
        ]

        delay_rst = Signal()
        delay_master_inc = Signal()
        delay_master_ce = Signal()
        delay_slave_inc = Signal()
        delay_slave_ce = Signal()

        # master serdes
        serdes_m_i_delayed = Signal()
        serdes_m_q = Signal(8)
        serdes_m_d = Signal(8)
        serdes_m_cntvalue = Signal(5)
        self.specials += [
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0, p_PIPE_SEL="FALSE",
                p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,

                i_C=ClockSignal("pix1p25x"),
                i_LD=delay_rst,
                i_CE=delay_master_ce,
                i_LDPIPEEN=0, i_INC=delay_master_inc,

                i_IDATAIN=serdes_m_i_nodelay, o_DATAOUT=serdes_m_i_delayed,
                o_CNTVALUEOUT=serdes_m_cntvalue
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=serdes_m_i_delayed,
                i_CE1=1,
                i_RST=ResetSignal("pix1p25x"),
                i_CLK=ClockSignal("pix5x"), i_CLKB=ClockSignal("pix5x_inv"),
                i_CLKDIV=ClockSignal("pix1p25x"),
                i_BITSLIP=0,
                o_Q8=serdes_m_q[0], o_Q7=serdes_m_q[1],
                o_Q6=serdes_m_q[2], o_Q5=serdes_m_q[3],
                o_Q4=serdes_m_q[4], o_Q3=serdes_m_q[5],
                o_Q2=serdes_m_q[6], o_Q1=serdes_m_q[7]
            ),
        ]

        # slave serdes
        # idelay_value must be preloaded with a 90° phase shift but we
        # do it dynamically by software to support all resolutions
        serdes_s_i_delayed = Signal()
        serdes_s_q = Signal(8)
        serdes_s_d = Signal(8)
        serdes_s_cntvalue = Signal(5)
        self.specials += [
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0, p_PIPE_SEL="FALSE",
                p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,

                i_C=ClockSignal("pix1p25x"),
                i_LD=delay_rst,
                i_CE=delay_slave_ce,
                i_LDPIPEEN=0, i_INC=delay_slave_inc,

                i_IDATAIN=serdes_s_i_nodelay, o_DATAOUT=serdes_s_i_delayed,
                o_CNTVALUEOUT=serdes_s_cntvalue
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=serdes_s_i_delayed,
                i_CE1=1,
                i_RST=ResetSignal("pix1p25x"),
                i_CLK=ClockSignal("pix5x"), i_CLKB=ClockSignal("pix5x_inv"),
                i_CLKDIV=ClockSignal("pix1p25x"),
                i_BITSLIP=0,
                o_Q8=serdes_s_q[0], o_Q7=serdes_s_q[1],
                o_Q6=serdes_s_q[2], o_Q5=serdes_s_q[3],
                o_Q4=serdes_s_q[4], o_Q3=serdes_s_q[5],
                o_Q2=serdes_s_q[6], o_Q1=serdes_s_q[7]
            ),
        ]

        # cntvalue sync
        self.submodules.sync_mcntvalue = BusSynchronizer(5, "pix1p25x", "sys")
        self.submodules.sync_scntvalue = BusSynchronizer(5, "pix1p25x", "sys")
        self.comb += [
            self.sync_mcntvalue.i.eq(serdes_m_cntvalue),
            self._cntvalueout_m.status.eq(self.sync_mcntvalue.o),
            self.sync_scntvalue.i.eq(serdes_s_cntvalue),
            self._cntvalueout_s.status.eq(self.sync_scntvalue.o),
        ]

        # polarity
        if hasattr(pad_p, "inverted"):
            self.comb += [
                serdes_m_d.eq(~serdes_m_q),
                serdes_s_d.eq(serdes_s_q)
            ]
        else:
            self.comb += [
                serdes_m_d.eq(serdes_m_q),
                serdes_s_d.eq(~serdes_s_q)
            ]

        # datapath
        self.submodules.gearbox = Gearbox(8, "pix1p25x", 10, "pix")
        self.comb += [
            self.gearbox.i.eq(serdes_m_d),
            self.d.eq(self.gearbox.o)
        ]

        # phase detector
        self.submodules.phase_detector = ClockDomainsRenamer("pix1p25x")(
            S7PhaseDetector())
        self.comb += [
            self.phase_detector.mdata.eq(serdes_m_d),
            self.phase_detector.sdata.eq(serdes_s_d)
        ]

        # phase error accumulator
        lateness = Signal(ntbits, reset=2**(ntbits - 1))
        too_late = Signal()
        too_early = Signal()
        reset_lateness = Signal()
        self.comb += [
            too_late.eq(lateness == (2**ntbits - 1)),
            too_early.eq(lateness == 0)
        ]
        self.sync.pix1p25x += [
            If(reset_lateness,
                lateness.eq(2**(ntbits - 1))
            ).Elif(~too_late & ~too_early,
                If(self.phase_detector.dec, lateness.eq(lateness + 1)),
                If(self.phase_detector.inc, lateness.eq(lateness - 1))
            )
        ]

        # delay control
        self.submodules.do_delay_rst = PulseSynchronizer("sys", "pix1p25x")
        self.submodules.do_delay_master_inc = PulseSynchronizer("sys", "pix1p25x")
        self.submodules.do_delay_master_dec = PulseSynchronizer("sys", "pix1p25x")
        self.submodules.do_delay_slave_inc = PulseSynchronizer("sys", "pix1p25x")
        self.submodules.do_delay_slave_dec = PulseSynchronizer("sys", "pix1p25x")
        self.comb += [
            delay_rst.eq(self.do_delay_rst.o),
            delay_master_inc.eq(self.do_delay_master_inc.o),
            delay_master_ce.eq(self.do_delay_master_inc.o | self.do_delay_master_dec.o),
            delay_slave_inc.eq(self.do_delay_slave_inc.o),
            delay_slave_ce.eq(self.do_delay_slave_inc.o | self.do_delay_slave_dec.o)
        ]

        self.comb += [
            self.do_delay_rst.i.eq(self._dly_ctl.re & self._dly_ctl.r[0]),
            self.do_delay_master_inc.i.eq(self._dly_ctl.re & self._dly_ctl.r[1]),
            self.do_delay_master_dec.i.eq(self._dly_ctl.re & self._dly_ctl.r[2]),
            self.do_delay_slave_inc.i.eq(self._dly_ctl.re & self._dly_ctl.r[3]),
            self.do_delay_slave_dec.i.eq(self._dly_ctl.re & self._dly_ctl.r[4])
        ]

        # phase detector control
        self.specials += MultiReg(Cat(too_late, too_early), self._phase.status)
        self.submodules.do_reset_lateness = PulseSynchronizer("sys", "pix1p25x")
        self.comb += [
            reset_lateness.eq(self.do_reset_lateness.o),
            self.do_reset_lateness.i.eq(self._phase_reset.re)
        ]
