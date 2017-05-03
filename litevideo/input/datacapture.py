from litex import *
from litex.gen.genlib.cdc import MultiReg, PulseSynchronizer
from litex.gen.genlib.misc import WaitTimer, BitSlip

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
        self.sync.pix += self.d.eq(dsr)


# TODO: to be removed when we'll have the phase detector working
class S7Alignment(Module):
    def __init__(self, symbol):
        self.delay_value = Signal(5)
        self.delay_ce = Signal()
        self.bitslip_value = Signal(4)

        # # #

        self.invalid = invalid = Signal()

        valid_symbols = [
            0b1111111111, 0b0100000000, 0b0111111111, 0b1100000000,
            0b0111111110, 0b1100000001, 0b1111111110, 0b0100000001,
            0b0111111100, 0b1100000011, 0b1111111100, 0b0100000011,
            0b1111111101, 0b0100000010, 0b0111111101, 0b1100000010,
            0b0111111000, 0b1100000111, 0b1111111000, 0b0100000111,
            0b1111111001, 0b0100000110, 0b0111111001, 0b1100000110,
            0b1111111011, 0b0100000100, 0b0111111011, 0b1100000100,
            0b0111111010, 0b1100000101, 0b1111111010, 0b0100000101,
            0b0111110000, 0b0100001111, 0b1111110001, 0b0100001110,
            0b0111110001, 0b1100001110, 0b1111110011, 0b0100001100,
            0b0111110011, 0b1100001100, 0b0111110010, 0b1100001101,
            0b1111110010, 0b0100001101, 0b1111110111, 0b0100001000,
            0b0111110111, 0b1100001000, 0b0111110110, 0b1100001001,
            0b1111110110, 0b0100001001, 0b0111110100, 0b1100001011,
            0b1111110100, 0b0100001011, 0b1001011111, 0b0010100000,
            0b0001011111, 0b1010100000, 0b1100011111, 0b0111100000,
            0b0100011111, 0b1111100000, 0b0100011110, 0b0111100001,
            0b1111100011, 0b0100011100, 0b0111100011, 0b1100011100,
            0b0111100010, 0b0100011101, 0b1111100111, 0b0100011000,
            0b0111100111, 0b1100011000, 0b0111100110, 0b1100011001,
            0b1111100110, 0b0100011001, 0b0111100100, 0b0100011011,
            0b1001001111, 0b0010110000, 0b0001001111, 0b1010110000,
            0b1111101111, 0b0100010000, 0b0111101111, 0b1100010000,
            0b0111101110, 0b1100010001, 0b1111101110, 0b0100010001,
            0b0111101100, 0b1100010011, 0b1111101100, 0b0100010011,
            0b1001000111, 0b1010111000, 0b0111101000, 0b0100010111,
            0b0010111100, 0b1001000011, 0b1010111100, 0b0001000011,
            0b0010111110, 0b1001000001, 0b1010111110, 0b0001000001,
            0b1010111111, 0b0001000000, 0b0010111111, 0b1001000000,
            0b1100111111, 0b0111000000, 0b0100111111, 0b1111000000,
            0b0100111110, 0b1111000001, 0b1100111110, 0b0111000001,
            0b0100111100, 0b0111000011, 0b1100111101, 0b0111000010,
            0b0100111101, 0b1111000010, 0b1111000111, 0b0100111000,
            0b0111000111, 0b1100111000, 0b0111000110, 0b0100111001,
            0b1100111011, 0b0111000100, 0b0100111011, 0b1111000100,
            0b1001101111, 0b0010010000, 0b0001101111, 0b1010010000,
            0b1111001111, 0b0100110000, 0b0111001111, 0b1100110000,
            0b0111001110, 0b1100110001, 0b1111001110, 0b0100110001,
            0b0111001100, 0b0100110011, 0b1001100111, 0b0010011000,
            0b0001100111, 0b1010011000, 0b1100110111, 0b0111001000,
            0b0100110111, 0b1111001000, 0b1001100011, 0b1010011100,
            0b0010011110, 0b1001100001, 0b1010011110, 0b0001100001,
            0b1010011111, 0b0001100000, 0b0010011111, 0b1001100000,
            0b1111011111, 0b0100100000, 0b0111011111, 0b1100100000,
            0b0111011110, 0b1100100001, 0b1111011110, 0b0100100001,
            0b0111011100, 0b1100100011, 0b1111011100, 0b0100100011,
            0b1001110111, 0b0010001000, 0b0001110111, 0b1010001000,
            0b0111011000, 0b0100100111, 0b1001110011, 0b0010001100,
            0b0001110011, 0b1010001100, 0b1001110001, 0b1010001110,
            0b1010001111, 0b0001110000, 0b0010001111, 0b1001110000,
            0b1100101111, 0b0111010000, 0b0100101111, 0b1111010000,
            0b1001111011, 0b0010000100, 0b0001111011, 0b1010000100,
            0b1001111001, 0b0010000110, 0b0001111001, 0b1010000110,
            0b1010000111, 0b1001111000, 0b1001111101, 0b0010000010,
            0b0001111101, 0b1010000010, 0b0001111100, 0b1010000011,
            0b1001111100, 0b0010000011, 0b0001111110, 0b1010000001,
            0b1001111110, 0b0010000001, 0b1001111111, 0b0010000000,
            0b0001111111, 0b1010000000, 0b1101111111, 0b0110000000,
            0b0101111111, 0b1110000000, 0b0101111110, 0b1110000001,
            0b1101111110, 0b0110000001, 0b0101111100, 0b1110000011,
            0b1101111100, 0b0110000011, 0b1101111101, 0b0110000010,
            0b0101111101, 0b1110000010, 0b0101111000, 0b0110000111,
            0b1101111001, 0b0110000110, 0b0101111001, 0b1110000110,
            0b1101111011, 0b0110000100, 0b0101111011, 0b1110000100,
            0b1000101111, 0b0011010000, 0b0000101111, 0b1011010000,
            0b1110001111, 0b0101110000, 0b0110001111, 0b1101110000,
            0b0110001110, 0b0101110001, 0b1101110011, 0b0110001100,
            0b0101110011, 0b1110001100, 0b1000100111, 0b1011011000,
            0b1101110111, 0b0110001000, 0b0101110111, 0b1110001000,
            0b0011011100, 0b1000100011, 0b1011011100, 0b0000100011,
            0b0011011110, 0b1000100001, 0b1011011110, 0b0000100001,
            0b1011011111, 0b0000100000, 0b0011011111, 0b1000100000,
            0b1110011111, 0b0101100000, 0b0110011111, 0b1101100000,
            0b0110011110, 0b1101100001, 0b1110011110, 0b0101100001,
            0b0110011100, 0b0101100011, 0b1000110111, 0b0011001000,
            0b0000110111, 0b1011001000, 0b1101100111, 0b0110011000,
            0b0101100111, 0b1110011000, 0b1000110011, 0b1011001100,
            0b0011001110, 0b1000110001, 0b1011001110, 0b0000110001,
            0b1011001111, 0b0000110000, 0b0011001111, 0b1000110000,
            0b1101101111, 0b0110010000, 0b0101101111, 0b1110010000,
            0b1000111011, 0b0011000100, 0b0000111011, 0b1011000100,
            0b1000111001, 0b1011000110, 0b1011000111, 0b0000111000,
            0b0011000111, 0b1000111000, 0b1000111101, 0b0011000010,
            0b0000111101, 0b1011000010, 0b1011000011, 0b1000111100,
            0b0000111110, 0b1011000001, 0b1000111110, 0b0011000001,
            0b1000111111, 0b0011000000, 0b0000111111, 0b1011000000,
            0b1110111111, 0b0101000000, 0b0110111111, 0b1101000000,
            0b0110111110, 0b1101000001, 0b1110111110, 0b0101000001,
            0b0110111100, 0b1101000011, 0b1110111100, 0b0101000011,
            0b1000010111, 0b1011101000, 0b0110111000, 0b0101000111,
            0b0011101100, 0b1000010011, 0b1011101100, 0b0000010011,
            0b0011101110, 0b1000010001, 0b1011101110, 0b0000010001,
            0b1011101111, 0b0000010000, 0b0011101111, 0b1000010000,
            0b1101001111, 0b0110110000, 0b0101001111, 0b1110110000,
            0b1000011011, 0b1011100100, 0b0011100110, 0b1000011001,
            0b1011100110, 0b0000011001, 0b1011100111, 0b0000011000,
            0b0011100111, 0b1000011000, 0b1000011101, 0b1011100010,
            0b1011100011, 0b0000011100, 0b0011100011, 0b1000011100,
            0b1011100001, 0b1000011110, 0b1000011111, 0b0011100000,
            0b0000011111, 0b1011100000, 0b1101011111, 0b0110100000,
            0b0101011111, 0b1110100000, 0b0011110100, 0b1000001011,
            0b1011110100, 0b0000001011, 0b0011110110, 0b1000001001,
            0b1011110110, 0b0000001001, 0b1011110111, 0b0000001000,
            0b0011110111, 0b1000001000, 0b0011110010, 0b1000001101,
            0b1011110010, 0b0000001101, 0b1011110011, 0b0000001100,
            0b0011110011, 0b1000001100, 0b1011110001, 0b0000001110,
            0b0011110001, 0b1000001110, 0b1000001111, 0b1011110000,
            0b0011111010, 0b1000000101, 0b1011111010, 0b0000000101,
            0b1011111011, 0b0000000100, 0b0011111011, 0b1000000100,
            0b1011111001, 0b0000000110, 0b0011111001, 0b1000000110,
            0b0011111000, 0b1000000111, 0b1011111000, 0b0000000111,
            0b1011111101, 0b0000000010, 0b0011111101, 0b1000000010,
            0b0011111100, 0b1000000011, 0b1011111100, 0b0000000011,
            0b0011111110, 0b1000000001, 0b1011111110, 0b0000000001,
            0b1011111111, 0b0000000000, 0b0011111111, 0b1000000000,
            0b0010101011, 0b0101010100, 0b1010101011, 0b1101010100]

        self.comb += invalid.eq(1)
        for s in valid_symbols:
            self.comb += If(symbol == s, invalid.eq(0))

        count = Signal(20)
        signal_quality = Signal(28)
        holdoff = Signal(10)
        error_seen = Signal()

        self.sync.pix += [
            error_seen.eq(0),
            If(holdoff == 0,
                If(invalid,
                    error_seen.eq(1)
                )
            ).Else(
                holdoff.eq(holdoff-1)
            ),
            self.delay_ce.eq(0),
            If(error_seen,
                If(signal_quality[24:28] == 0xf,
                    holdoff.eq(2**10-1),
                    If(self.delay_value == 31,
                        self.bitslip_value.eq(self.bitslip_value+1)
                    ),
                    self.delay_value.eq(self.delay_value+1),
                    self.delay_ce.eq(1),
                    signal_quality[24:28].eq(0x4)
                ).Else(
                    signal_quality.eq(signal_quality + 0x100000)
                )
            ).Else(
                If(signal_quality[24:28] != 0,
                    signal_quality.eq(signal_quality-1)
                )
            )
        ]


class S7DataCapture(Module):
    def __init__(self, pad_p, pad_n):
        self.d = Signal(10)

        # # #

        # IO
        pad_se = Signal()
        self.specials += Instance("IBUFDS",
                                  i_I=pad_p, i_IB=pad_n,
                                  o_O=pad_se)

        pad_delayed_master = Signal()
        shiftout_master = Signal(2)

        self.submodules.alignment = alignment = S7Alignment(self.d)

        self.submodules.bitslip = bitslip = ClockDomainsRenamer("pix")(BitSlip(10))
        self.comb += bitslip.value.eq(alignment.delay_value)

        self.specials += [
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                p_PIPE_SEL="FALSE", p_IDELAY_TYPE="VAR_LOAD", p_IDELAY_VALUE=0,

                i_C=ClockSignal("pix"),
                i_LD=1,
                i_CE=alignment.delay_ce,
                i_LDPIPEEN=0, i_INC=0,
                i_CINVCTRL=0, i_CNTVALUEIN=alignment.delay_value,

                i_IDATAIN=pad_se, o_DATAOUT=pad_delayed_master
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=10, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=pad_delayed_master,
                i_CE1=1, i_CE2=1,
                i_RST=ResetSignal("pix"),
                i_CLK=ClockSignal("pix5x"), i_CLKB=~ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_BITSLIP=0,

                o_Q1=bitslip.i[9], o_Q2=bitslip.i[8],
                o_Q3=bitslip.i[7], o_Q4=bitslip.i[6],
                o_Q5=bitslip.i[5], o_Q6=bitslip.i[4],
                o_Q7=bitslip.i[3], o_Q8=bitslip.i[2],

                o_SHIFTOUT1=shiftout_master[0], o_SHIFTOUT2=shiftout_master[1],
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=10, p_DATA_RATE="DDR",
                p_SERDES_MODE="SLAVE", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=0,
                i_CE1=1, i_CE2=1,
                i_RST=ResetSignal("pix"),
                i_CLK=ClockSignal("pix5x"), i_CLKB=~ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_BITSLIP=0,

                o_SHIFTIN1=shiftout_master[0], o_SHIFTIN2=shiftout_master[1],

                #o_Q1=, o_Q2=,
                o_Q3=bitslip.i[1], o_Q4=bitslip.i[0],
                #o_Q5=, o_Q6=,
                #o_Q7=, o_Q8=
            ),
        ]
        self.comb += self.d.eq(bitslip.o)
